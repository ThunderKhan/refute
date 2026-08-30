from __future__ import annotations

import json
from pathlib import Path

from refute.agents.challenger_v4 import compile_intent_to_pytest_v4, generate_challenge_intent_v4
from refute.case import load_case
from refute.models import Verdict
from refute.verify_v4 import verify_case_v4


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _case(tmp_path: Path, *, case_id: str, issue: str, original_app: str, patched_app: str, public_test: str):
    root = tmp_path / case_id
    for version, app in (("original", original_app), ("patched", patched_app)):
        version_dir = root / version
        version_dir.mkdir(parents=True)
        (version_dir / "app.py").write_text(app, encoding="utf-8")
        (version_dir / "test_app.py").write_text(public_test, encoding="utf-8")
    (root / "issue.md").write_text(issue, encoding="utf-8")
    (root / "case.json").write_text(
        json.dumps({"case_id": case_id, "test_command": ["python", "-m", "pytest", "-q"]}),
        encoding="utf-8",
    )
    return load_case(root)


def _intent(*, contract_id: str, target: str, args: list, kind: str = "remaining_requirement", expectation: dict, rationale: str = "nearby contract case") -> str:
    return json.dumps({
        "kind": kind,
        "contract_id": contract_id,
        "target": target,
        "args": args,
        "expectation": expectation,
        "rationale": rationale,
    })


def _critique(supported: bool) -> str:
    return json.dumps({"supported": supported, "reason": "directly supported" if supported else "not entailed"})


def test_v4_compiles_structured_equals_intent(tmp_path: Path):
    case = _case(
        tmp_path,
        case_id="intent_compile",
        issue="Values from 0 through 100 inclusive are valid.",
        original_app="def normalize_percentage(value):\n    return value\n",
        patched_app="def normalize_percentage(value):\n    return value\n",
        public_test="from app import normalize_percentage\n\ndef test_public():\n    assert normalize_percentage(0) == 0\n",
    )
    llm = SequencedLLM([_intent(contract_id="c1", target="normalize_percentage", args=[100], expectation={"type": "equals", "value": 100})])
    intent = generate_challenge_intent_v4(case, llm, attempt=1)
    code = compile_intent_to_pytest_v4(intent)
    assert "normalize_percentage(100)" in code
    assert "== 100" in code


def test_v4_finds_partial_fix_from_supported_boundary_intent(tmp_path: Path):
    case = _case(
        tmp_path,
        case_id="partial_boundary_v4",
        issue="Values from 0 through 100 inclusive are valid. The implementation rejects both boundaries.",
        original_app=(
            "def normalize_percentage(value):\n"
            "    if value <= 0 or value >= 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        patched_app=(
            "def normalize_percentage(value):\n"
            "    if value < 0 or value >= 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        public_test="from app import normalize_percentage\n\ndef test_zero():\n    assert normalize_percentage(0) == 0\n",
    )
    llm = SequencedLLM([
        _intent(contract_id="c1", target="normalize_percentage", args=[100], expectation={"type": "equals", "value": 100}),
        _critique(True),
    ])
    result = verify_case_v4(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.PARTIAL_FIX
    assert len(result.challenge_executions) == 1
    assert result.challenge_executions[0].classification == "remaining_requirement_counterexample"


def test_v4_finds_regression_from_supported_preservation_intent(tmp_path: Path):
    case = _case(
        tmp_path,
        case_id="spacing_regression_v4",
        issue="Trim surrounding whitespace while preserving meaningful internal spaces.",
        original_app="def format_username(value):\n    return value.lower()\n",
        patched_app="def format_username(value):\n    return value.strip().replace(' ', '').lower()\n",
        public_test="from app import format_username\n\ndef test_trim():\n    assert format_username(' Alice ') == 'alice'\n",
    )
    llm = SequencedLLM([
        _intent(
            contract_id="c1",
            target="format_username",
            args=["Mary Jane"],
            kind="regression_guard",
            expectation={"type": "equals", "value": "mary jane"},
        ),
        _critique(True),
    ])
    result = verify_case_v4(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.REGRESSION_INTRODUCED
    assert result.challenge_executions[0].classification == "regression_counterexample"


def test_v4_requires_two_distinct_supported_survivors_for_complete(tmp_path: Path):
    case = _case(
        tmp_path,
        case_id="complete_v4",
        issue="Every integer from 0 through 100 inclusive is valid. Values below 0 or above 100 raise ValueError.",
        original_app=(
            "def clamp_percentage(value):\n"
            "    if value <= 0 or value > 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        patched_app=(
            "def clamp_percentage(value):\n"
            "    if value < 0 or value > 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        public_test="from app import clamp_percentage\n\ndef test_zero():\n    assert clamp_percentage(0) == 0\n",
    )
    llm = SequencedLLM([
        _intent(contract_id="c1", target="clamp_percentage", args=[100], expectation={"type": "equals", "value": 100}),
        _critique(True),
        _intent(contract_id="c2", target="clamp_percentage", args=[-1], kind="regression_guard", expectation={"type": "raises", "exception": "ValueError"}),
        _critique(True),
    ])
    result = verify_case_v4(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.COMPLETE_FIX
    assert [item.classification for item in result.challenge_executions] == ["survived", "survived"]
