from __future__ import annotations

import ast
import json
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .challenger_v32 import ContractSpan, extract_contract_spans
from .reproducer import _extract_json_object


SYSTEM_PROMPT = """You are the Challenger in a software patch verification system.
Your job is to propose ONE nearby falsification INTENT for a patch whose public reported trigger now passes.

Do NOT write Python code. Select only from the supplied contract IDs and public callable targets. The harness will compile your structured intent into a pytest test deterministically.

Return exactly one JSON object:
{
  "kind": "remaining_requirement | regression_guard",
  "contract_id": "c1",
  "target": "function_name",
  "args": [JSON values only],
  "expectation": {
    "type": "equals | raises | len_lte_arg",
    "value": "required only for equals",
    "exception": "required only for raises",
    "arg_index": 0
  },
  "rationale": "brief explanation"
}

Expectation meanings:
- equals: target(*args) must equal the supplied JSON value.
- raises: target(*args) must raise the named built-in exception (for example TypeError or ValueError).
- len_lte_arg: len(target(*args)) must be <= args[arg_index].

Rules:
- contract_id MUST be one of the supplied contract spans;
- target MUST be one of the supplied public callable targets;
- test a nearby behavior justified by the selected contract, not the already-repaired public trigger;
- use only JSON-serializable argument/expected values;
- do not invent benchmark internals, hidden tests, expected verdicts, source code, or pytest syntax;
- prefer boundaries, preserved invariants, small limits, or exception specificity when supported by the issue;
- output syntactically valid JSON with no surrounding commentary.
"""


class ChallengeIntentErrorV4(ValueError):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True, slots=True)
class ChallengeIntentV4:
    attempt: int
    kind: str
    contract_id: str
    contract_text: str
    target: str
    args: tuple[object, ...]
    expectation_type: str
    expected_value: object | None
    expected_exception: str | None
    arg_index: int | None
    rationale: str
    raw_response: str


def discover_public_targets(case: VerificationCase) -> tuple[str, ...]:
    test_file = case.original_path / "test_app.py"
    if not test_file.is_file():
        return ()
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ()

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app":
            for alias in node.names:
                name = alias.asname or alias.name
                if name not in names:
                    names.append(name)
    return tuple(names)


def build_challenger_prompt_v4(
    case: VerificationCase,
    *,
    attempt: int,
    feedback: str | None = None,
) -> tuple[str, tuple[ContractSpan, ...], tuple[str, ...]]:
    diff = build_static_diff(case) or "(No source differences detected.)"
    spans = extract_contract_spans(case.issue_text)
    targets = discover_public_targets(case)
    parts = [
        f"ATTEMPT: {attempt}",
        f"ISSUE REPORT:\n{case.issue_text.strip()}",
        "CONTRACT SPANS:\n" + json.dumps(
            [{"contract_id": span.contract_id, "text": span.text} for span in spans], indent=2
        ),
        "PUBLIC CALLABLE TARGETS:\n" + json.dumps(list(targets), indent=2),
        f"PATCH DIFF:\n```diff\n{diff}\n```",
        "PUBLIC EXECUTION FACT: the reported public trigger changed from FAIL on the original to PASS on the patch.",
        "Propose one nearby structured falsification intent. Do not emit Python code.",
    ]
    if feedback:
        parts.append(f"PRIOR INTENT FEEDBACK:\n{feedback}")
    return "\n\n".join(parts) + "\n", spans, targets


def generate_challenge_intent_v4(
    case: VerificationCase,
    llm: LLM,
    *,
    attempt: int,
    feedback: str | None = None,
) -> ChallengeIntentV4:
    prompt, spans, targets = build_challenger_prompt_v4(case, attempt=attempt, feedback=feedback)
    raw = llm.complete(SYSTEM_PROMPT, prompt)
    try:
        payload = _extract_json_object(raw)
        kind = payload.get("kind")
        contract_id = payload.get("contract_id")
        target = payload.get("target")
        args = payload.get("args")
        expectation = payload.get("expectation")
        rationale = payload.get("rationale")

        if kind not in {"remaining_requirement", "regression_guard"}:
            raise ValueError("intent kind must be remaining_requirement or regression_guard")
        by_id = {span.contract_id: span for span in spans}
        if not isinstance(contract_id, str) or contract_id not in by_id:
            raise ValueError("intent contract_id must select a supplied contract span")
        if not isinstance(target, str) or target not in targets:
            raise ValueError("intent target must select a supplied public callable target")
        if not isinstance(args, list):
            raise ValueError("intent args must be a JSON array")
        # Round-trip check rejects model-specific/non-JSON Python values.
        json.dumps(args)
        if not isinstance(expectation, dict):
            raise ValueError("intent expectation must be a JSON object")
        expectation_type = expectation.get("type")
        if expectation_type not in {"equals", "raises", "len_lte_arg"}:
            raise ValueError("intent expectation type must be equals, raises, or len_lte_arg")

        expected_value: object | None = None
        expected_exception: str | None = None
        arg_index: int | None = None
        if expectation_type == "equals":
            if "value" not in expectation:
                raise ValueError("equals expectation requires value")
            expected_value = expectation.get("value")
            json.dumps(expected_value)
        elif expectation_type == "raises":
            value = expectation.get("exception")
            allowed = {"TypeError", "ValueError", "KeyError", "IndexError", "ZeroDivisionError"}
            if not isinstance(value, str) or value not in allowed:
                raise ValueError("raises expectation uses an unsupported exception")
            expected_exception = value
        else:
            value = expectation.get("arg_index")
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(args):
                raise ValueError("len_lte_arg expectation requires a valid arg_index")
            if not isinstance(args[value], int) or isinstance(args[value], bool):
                raise ValueError("len_lte_arg referenced argument must be an integer")
            arg_index = value

        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("intent rationale must be a non-empty string")

        selected = by_id[contract_id]
        return ChallengeIntentV4(
            attempt=attempt,
            kind=kind,
            contract_id=contract_id,
            contract_text=selected.text,
            target=target,
            args=tuple(args),
            expectation_type=expectation_type,
            expected_value=expected_value,
            expected_exception=expected_exception,
            arg_index=arg_index,
            rationale=rationale.strip(),
            raw_response=raw,
        )
    except (TypeError, ValueError) as exc:
        raise ChallengeIntentErrorV4(str(exc), raw) from exc


def compile_intent_to_pytest_v4(intent: ChallengeIntentV4) -> str:
    args_literal = ", ".join(repr(value) for value in intent.args)
    call = f"{intent.target}({args_literal})"
    imports = [f"from app import {intent.target}"]

    if intent.expectation_type == "equals":
        if intent.expected_value is None:
            assertion = f"assert {call} is None"
        else:
            assertion = f"assert {call} == {repr(intent.expected_value)}"
    elif intent.expectation_type == "raises":
        imports.insert(0, "import pytest")
        assertion = (
            f"with pytest.raises({intent.expected_exception}):\n"
            f"        {call}"
        )
    else:
        assert intent.arg_index is not None
        assertion = f"assert len({call}) <= {repr(intent.args[intent.arg_index])}"

    if "\n" in assertion:
        body = "    " + assertion.replace("\n", "\n    ")
    else:
        body = "    " + assertion
    return "\n".join(imports) + "\n\n\ndef test_refute_challenge():\n" + body + "\n"
