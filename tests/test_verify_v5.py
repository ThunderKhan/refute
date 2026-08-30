from __future__ import annotations

import json
from pathlib import Path

from refute.agents.probe_compiler_v5 import compile_contract_probes_v5
from refute.case import load_case
from refute.models import Verdict
from refute.verify_v5 import verify_case_v5


class FixedPlannerLLM:
    def __init__(self, response: str = "p1,p2"):
        self.response = response
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.response


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


def test_compiler_builds_inclusive_range_probes(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="range",
        issue="normalize should accept values from 0 through 100 inclusive.",
        original_app="def normalize(value):\n    if value <= 0 or value >= 100: raise ValueError\n    return value\n",
        patched_app="def normalize(value):\n    if value < 0 or value >= 100: raise ValueError\n    return value\n",
        public_test="from app import normalize\n\ndef test_zero():\n    assert normalize(0) == 0\n",
    )
    probes = compile_contract_probes_v5(case)
    assert len(probes) >= 2
    assert "normalize(100)" in probes[0].test_code
    assert probes[0].kind == "remaining_requirement"


def test_v5_detects_partial_upper_boundary(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="partial",
        issue="normalize should accept values from 0 through 100 inclusive.",
        original_app="def normalize(value):\n    if value <= 0 or value >= 100: raise ValueError\n    return value\n",
        patched_app="def normalize(value):\n    if value < 0 or value >= 100: raise ValueError\n    return value\n",
        public_test="from app import normalize\n\ndef test_zero():\n    assert normalize(0) == 0\n",
    )
    result = verify_case_v5(case, FixedPlannerLLM(), artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.challenge_executions[0].classification == "remaining_requirement_counterexample"


def test_v5_detects_internal_space_regression(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="spaces",
        issue="format_username should normalize case and remove leading or trailing whitespace while preserving meaningful internal spaces.",
        original_app="def format_username(value):\n    return value.lower()\n",
        patched_app="def format_username(value):\n    return value.strip().replace(' ', '').lower()\n",
        public_test="from app import format_username\n\ndef test_trim():\n    assert format_username(' Alice ') == 'alice'\n",
    )
    result = verify_case_v5(case, FixedPlannerLLM(), artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.REGRESSION_INTRODUCED
    assert result.challenge_executions[0].classification == "regression_counterexample"


def test_v5_requires_two_survivors_for_complete_fix(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="complete",
        issue="clamp should accept every integer from 0 through 100 inclusive.",
        original_app="def clamp(value):\n    if value <= 0 or value > 100: raise ValueError\n    return value\n",
        patched_app="def clamp(value):\n    if value < 0 or value > 100: raise ValueError\n    return value\n",
        public_test="from app import clamp\n\ndef test_zero():\n    assert clamp(0) == 0\n",
    )
    result = verify_case_v5(case, FixedPlannerLLM(), artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.verdict is Verdict.COMPLETE_FIX
    assert len(result.challenge_executions) == 2
    assert all(item.classification == "survived" for item in result.challenge_executions)


def test_v5_planner_text_failure_falls_back_to_compiled_order(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="fallback",
        issue="clamp should accept every integer from 0 through 100 inclusive.",
        original_app="def clamp(value):\n    if value <= 0 or value > 100: raise ValueError\n    return value\n",
        patched_app="def clamp(value):\n    if value < 0 or value > 100: raise ValueError\n    return value\n",
        public_test="from app import clamp\n\ndef test_zero():\n    assert clamp(0) == 0\n",
    )
    result = verify_case_v5(case, FixedPlannerLLM("not valid ids"), artifacts_root=tmp_path / "artifacts", timeout_seconds=10)
    assert result.planner_fallback is True
    assert len(result.challenge_executions) == 2
