from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import ExecutionResult, Verdict
from refute.verify_v23 import analyze_test_delta, verify_case_v23


REPO_ROOT = Path(__file__).resolve().parents[1]


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _execution(*, passed: bool, failures: tuple[str, ...] = ()) -> ExecutionResult:
    stdout = "\n".join(f"FAILED {item} - AssertionError" for item in failures)
    return ExecutionResult(
        command=("python", "-m", "pytest", "-q"),
        cwd=Path("."),
        exit_code=0 if passed else 1,
        stdout=stdout,
        stderr="",
        duration_seconds=0.01,
        timed_out=False,
    )


def _investigator_payload() -> str:
    return json.dumps(
        {
            "expected_behavior": "0 through 100 inclusive are valid",
            "reported_failure": "0 is rejected",
            "trigger_conditions": ["value equals 0"],
            "likely_files": ["app.py"],
            "reproduction_strategy": "call clamp_percentage(0)",
            "risk_areas": ["lower boundary", "upper boundary"],
        }
    )


def _good_repro() -> str:
    return json.dumps(
        {
            "rationale": "Exercise the reported zero-boundary failure.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_zero_is_valid():\n"
                "    assert clamp_percentage(0) == 0\n"
            ),
        }
    )


def test_delta_marks_new_failures_as_regression():
    original = _execution(passed=False, failures=("test_app.py::test_reported_bug",))
    patched = _execution(
        passed=False,
        failures=("test_app.py::test_new_regression",),
    )
    delta = analyze_test_delta(original, patched)
    assert delta.classification == "new_regressions"
    assert delta.deterministic_verdict is Verdict.REGRESSION_INTRODUCED
    assert delta.fixed_tests == ("test_app.py::test_reported_bug",)
    assert delta.new_failures == ("test_app.py::test_new_regression",)


def test_delta_marks_partial_progress_when_some_failures_remain():
    original = _execution(
        passed=False,
        failures=("test_app.py::test_a", "test_app.py::test_b"),
    )
    patched = _execution(passed=False, failures=("test_app.py::test_b",))
    delta = analyze_test_delta(original, patched)
    assert delta.classification == "partial_progress"
    assert delta.deterministic_verdict is Verdict.PARTIAL_FIX
    assert delta.fixed_tests == ("test_app.py::test_a",)
    assert delta.remaining_failures == ("test_app.py::test_b",)


def test_delta_marks_same_failures_as_ineffective():
    failures = ("test_app.py::test_reported_bug",)
    delta = analyze_test_delta(
        _execution(passed=False, failures=failures),
        _execution(passed=False, failures=failures),
    )
    assert delta.classification == "no_observed_progress"
    assert delta.deterministic_verdict is Verdict.INEFFECTIVE_FIX


def test_v23_uses_reproduction_only_when_suite_delta_is_ambiguous(tmp_path: Path):
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The visible suite is repaired and the generated reproduction discriminates original from patch.",
        }
    )
    llm = SequencedLLM([_investigator_payload(), _good_repro(), verifier])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v23(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=2,
        run_id="v23-suite-repaired",
    )

    assert result.test_delta.classification == "suite_repaired"
    assert result.test_delta.deterministic_verdict is None
    assert result.discriminating_reproduction is not None
    assert result.verdict is Verdict.COMPLETE_FIX
    assert result.verifier_called is True
    assert len(llm.calls) == 3

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "advanced_iteration_2_3"
    assert manifest["capabilities"]["test_delta_engine"] is True


def test_v23_case_002_short_circuits_to_observed_partial_fix(tmp_path: Path):
    llm = SequencedLLM([_investigator_payload()])
    case = load_case(REPO_ROOT / "benchmark" / "case_002")

    result = verify_case_v23(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=2,
        run_id="v23-observed-partial",
    )

    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.test_delta.deterministic_verdict is Verdict.PARTIAL_FIX
    assert result.reproduction_attempts == ()
    assert result.verifier_called is False
    assert len(llm.calls) == 1
