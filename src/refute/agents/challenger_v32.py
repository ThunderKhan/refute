from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .reproducer import _extract_json_object, validate_generated_test

SYSTEM_PROMPT = """You are the Challenger in a software patch verification system.
Your job is to propose ONE nearby pytest falsification test for a patch whose public reported trigger now passes.

The user prompt includes deterministic CONTRACT SPANS extracted from the public issue report. Ground the test by selecting one contract_id from that supplied list. Do not copy or invent a quote.

Return exactly one JSON object:
{
  "kind": "remaining_requirement | regression_guard",
  "contract_id": "c1",
  "rationale": "brief explanation of how the selected contract span justifies this nearby test",
  "test_code": "complete pytest-compatible Python source"
}

Definitions:
- remaining_requirement: another requirement stated by the selected contract span may still fail on both original and patch.
- regression_guard: behavior protected by the selected contract span may pass on the original but fail on the patch.

Constraints:
- contract_id MUST be one of the supplied CONTRACT SPANS;
- do not test behavior outside the selected contract span;
- do NOT repeat the already repaired public trigger;
- prefer boundaries, preserved invariants, small-limit behavior, or exception specificity when the contract supports them;
- use only local project code and Python/pytest facilities;
- no network, subprocesses, shell commands, destructive file operations, eval, exec, or dynamic imports;
- do not modify project files;
- do not reference expected verdicts, evaluator oracles, hidden tests, or benchmark internals;
- JSON must be syntactically valid. No surrounding commentary.
"""


class ChallengeGenerationErrorV32(ValueError):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True, slots=True)
class ContractSpan:
    contract_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ChallengeCandidateV32:
    attempt: int
    kind: str
    contract_id: str
    contract_text: str
    rationale: str
    test_code: str
    raw_response: str


def extract_contract_spans(issue_text: str) -> tuple[ContractSpan, ...]:
    cleaned_lines: list[str] = []
    for raw_line in issue_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        cleaned_lines.append(line)

    sentences: list[str] = []
    for line in cleaned_lines:
        for piece in re.split(r"(?<=[.!?])\s+", line):
            text = piece.strip()
            if text:
                sentences.append(text)

    if not sentences:
        fallback = issue_text.strip()
        if fallback:
            sentences = [fallback]

    return tuple(
        ContractSpan(contract_id=f"c{index}", text=text)
        for index, text in enumerate(sentences, start=1)
    )


def build_challenger_prompt_v32(
    case: VerificationCase,
    *,
    attempt: int,
    feedback: str | None = None,
) -> tuple[str, tuple[ContractSpan, ...]]:
    diff = build_static_diff(case) or "(No source differences detected.)"
    spans = extract_contract_spans(case.issue_text)
    span_payload = [{"contract_id": span.contract_id, "text": span.text} for span in spans]
    parts = [
        f"ATTEMPT: {attempt}",
        f"ISSUE REPORT:\n{case.issue_text.strip()}",
        "CONTRACT SPANS:\n" + json.dumps(span_payload, indent=2),
        f"PATCH DIFF:\n```diff\n{diff}\n```",
        "PUBLIC EXECUTION FACT: the reported public trigger changed from FAIL on the original to PASS on the patch.",
        "Choose exactly one supplied contract_id and generate one different nearby falsification test.",
    ]
    if feedback:
        parts.append(f"PRIOR CHALLENGE FEEDBACK:\n{feedback}")
    return "\n\n".join(parts) + "\n", spans


def generate_challenge_v32(
    case: VerificationCase,
    llm: LLM,
    *,
    attempt: int,
    feedback: str | None = None,
) -> ChallengeCandidateV32:
    prompt, spans = build_challenger_prompt_v32(case, attempt=attempt, feedback=feedback)
    raw = llm.complete(SYSTEM_PROMPT, prompt)
    try:
        payload = _extract_json_object(raw)
        kind = payload.get("kind")
        contract_id = payload.get("contract_id")
        rationale = payload.get("rationale")
        test_code = payload.get("test_code")

        if kind not in {"remaining_requirement", "regression_guard"}:
            raise ValueError("challenger kind must be remaining_requirement or regression_guard")
        by_id = {span.contract_id: span for span in spans}
        if not isinstance(contract_id, str) or contract_id not in by_id:
            allowed = ", ".join(by_id) or "none"
            raise ValueError(f"challenger contract_id must be one of: {allowed}")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("challenger rationale must be a non-empty string")
        if not isinstance(test_code, str) or not test_code.strip():
            raise ValueError("challenger test_code must be a non-empty string")
        validate_generated_test(test_code)

        selected = by_id[contract_id]
        return ChallengeCandidateV32(
            attempt=attempt,
            kind=kind,
            contract_id=contract_id,
            contract_text=selected.text,
            rationale=rationale.strip(),
            test_code=test_code.rstrip() + "\n",
            raw_response=raw,
        )
    except ValueError as exc:
        raise ChallengeGenerationErrorV32(str(exc), raw) from exc
