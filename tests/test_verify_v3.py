from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify_v3 import verify_case_v3


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _investigation(expected: str, risk: str) -> str:
    return json.dumps(
        {
            "expected_behavior": expected,
            "reported_failure": "reported public trigger fails on original",
            "trigger_conditions": ["reported trigger"],
            "likely_files": ["app.py"],
            "reproduction_strategy": "exercise the reported trigger",
            "risk_areas": [risk],
        }
    )


def _make_case(tmp_path: Path, *, case_id: str, issue: str, original_app: str, patched_app: str, public_test: str):
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


def test_v3_finds_partial_fix_with_nearby_boundary(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="partial_boundary",
        issue="Values from 0 through 100 inclusive are valid; zero is currently rejected.",
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
    challenger = json.dumps(
        {
            "candidates": [
                {
                    "rationale": "The upper inclusive boundary is a nearby symmetric risk.",
                    "test_code": (
                        "from app import normalize_percentage\n\n"
                        "def test_upper_boundary():\n"
                        "    assert normalize_percentage(100) == 100\n"
                    ),
                }
            ]
        }
    )
    llm = SequencedLLM([
        _investigation("0 through 100 inclusive are valid", "upper boundary"),
        challenger,
    ])

    result = verify_case_v3(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)

    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.challenger_called is True
    assert len(result.challenge_executions) == 1
    assert result.challenge_executions[0].classification == "remaining_bug_counterexample"


def test_v3_finds_regression_when_nearby_invariant_breaks(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="spacing_regression",
        issue="Trim surrounding whitespace and lowercase text while preserving meaningful internal spaces.",
        original_app="def format_username(value):\n    return value.lower()\n",
        patched_app="def format_username(value):\n    return value.strip().replace(' ', '').lower()\n",
        public_test=(
            "from app import format_username\n\n"
            "def test_trim():\n"
            "    assert format_username(' Alice ') == 'alice'\n"
        ),
    )
    challenger = json.dumps(
        {
            "candidates": [
                {
                    "rationale": "Internal spaces are explicitly required to be preserved.",
                    "test_code": (
                        "from app import format_username\n\n"
                        "def test_internal_space():\n"
                        "    assert format_username('Mary Jane') == 'mary jane'\n"
                    ),
                }
            ]
        }
    )
    llm = SequencedLLM([
        _investigation("preserve internal spaces", "internal whitespace"),
        challenger,
    ])

    result = verify_case_v3(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)

    assert result.verdict is Verdict.REGRESSION_INTRODUCED
    assert result.challenge_executions[0].classification == "regression_counterexample"


def test_v3_keeps_both_pass_case_inconclusive_without_agent_calls(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="unreproduced",
        issue="An intermittent cache problem was reported without a reproducible trigger.",
        original_app="def value():\n    return 1\n",
        patched_app="def value():\n    return 1\n",
        public_test="from app import value\n\ndef test_value():\n    assert value() == 1\n",
    )
    llm = SequencedLLM([])

    result = verify_case_v3(case, llm, artifacts_root=tmp_path / "artifacts", timeout_seconds=10)

    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.challenger_called is False
    assert result.investigator_called is False
