from __future__ import annotations

import json
from pathlib import Path

from refute.agents.challenger_v32 import extract_contract_spans, generate_challenge_v32
from refute.case import load_case
from refute.models import Verdict
from refute.verify_v32 import verify_case_v32


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _make_case(tmp_path: Path, *, issue: str, original_app: str, patched_app: str, public_test: str):
    root = tmp_path / "case_x"
    for version, app in (("original", original_app), ("patched", patched_app)):
        version_dir = root / version
        version_dir.mkdir(parents=True)
        (version_dir / "app.py").write_text(app, encoding="utf-8")
        (version_dir / "test_app.py").write_text(public_test, encoding="utf-8")
    (root / "issue.md").write_text(issue, encoding="utf-8")
    (root / "case.json").write_text(
        json.dumps({"case_id": "case_x", "test_command": ["python", "-m", "pytest", "-q"]}),
        encoding="utf-8",
    )
    return load_case(root)


def test_extract_contract_spans_assigns_stable_ids():
    spans = extract_contract_spans("# Title\n\nZero is valid. Values up to 100 are valid.\n")
    assert [(span.contract_id, span.text) for span in spans] == [
        ("c1", "Zero is valid."),
        ("c2", "Values up to 100 are valid."),
    ]


def test_generate_v32_rejects_unknown_contract_id(tmp_path: Path):
    case = _make_case(
        tmp_path,
        issue="Zero through 100 inclusive are valid.",
        original_app="def f(x):\n    return x\n",
        patched_app="def f(x):\n    return x\n",
        public_test="from app import f\n\ndef test_x():\n    assert f(0) == 0\n",
    )
    llm = SequencedLLM([json.dumps({
        "kind": "remaining_requirement",
        "contract_id": "c99",
        "rationale": "upper boundary",
        "test_code": "from app import f\n\ndef test_100():\n    assert f(100) == 100\n",
    })])

    try:
        generate_challenge_v32(case, llm, attempt=1)
    except ValueError as exc:
        assert "contract_id" in str(exc)
    else:
        raise AssertionError("unknown contract id should be rejected")


def test_v32_finds_partial_fix_without_investigator(tmp_path: Path):
    case = _make_case(
        tmp_path,
        issue="Values from 0 through 100 inclusive are valid. Zero is currently rejected.",
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
        public_test=(
            "from app import normalize_percentage\n\n"
            "def test_zero():\n"
            "    assert normalize_percentage(0) == 0\n"
        ),
    )
    llm = SequencedLLM([json.dumps({
        "kind": "remaining_requirement",
        "contract_id": "c1",
        "rationale": "The inclusive range also requires the upper boundary.",
        "test_code": (
            "from app import normalize_percentage\n\n"
            "def test_upper_boundary():\n"
            "    assert normalize_percentage(100) == 100\n"
        ),
    })])

    result = verify_case_v32(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)

    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.investigator_called is False
    assert result.challenger_called is True
    assert result.challenge_executions[0].classification == "remaining_requirement_counterexample"


def test_v32_finds_regression_with_contract_id(tmp_path: Path):
    case = _make_case(
        tmp_path,
        issue="Trim surrounding whitespace while preserving meaningful internal spaces.",
        original_app="def format_username(value):\n    return value.lower()\n",
        patched_app="def format_username(value):\n    return value.strip().replace(' ', '').lower()\n",
        public_test=(
            "from app import format_username\n\n"
            "def test_trim():\n"
            "    assert format_username(' Alice ') == 'alice'\n"
        ),
    )
    llm = SequencedLLM([json.dumps({
        "kind": "regression_guard",
        "contract_id": "c1",
        "rationale": "Internal spaces are explicitly preserved by the contract.",
        "test_code": (
            "from app import format_username\n\n"
            "def test_internal_space():\n"
            "    assert format_username('Mary Jane') == 'mary jane'\n"
        ),
    })])

    result = verify_case_v32(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)

    assert result.verdict is Verdict.REGRESSION_INTRODUCED
    assert result.challenge_executions[0].classification == "regression_counterexample"
