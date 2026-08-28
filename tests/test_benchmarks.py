from pathlib import Path

import pytest

from refute.case import load_case
from refute.executor import run_command
from refute.models import Verdict


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"


@pytest.mark.parametrize(
    ("case_name", "expected_verdict", "original_passes", "patched_passes"),
    [
        ("case_001", Verdict.COMPLETE_FIX, False, True),
        ("case_002", Verdict.PARTIAL_FIX, False, False),
        ("case_003", Verdict.REGRESSION_INTRODUCED, False, False),
    ],
)
def test_seed_benchmarks_have_expected_execution_shape(
    case_name: str,
    expected_verdict: Verdict,
    original_passes: bool,
    patched_passes: bool,
):
    case = load_case(BENCHMARK_ROOT / case_name)

    original = run_command(case.test_command, case.original_path, timeout_seconds=10)
    patched = run_command(case.test_command, case.patched_path, timeout_seconds=10)

    assert case.expected_verdict is expected_verdict
    assert original.passed is original_passes
    assert patched.passed is patched_passes
