from __future__ import annotations

from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify_v24 import verify_case_v24


REPO_ROOT = Path(__file__).resolve().parents[1]


class FailIfCalledLLM:
    def complete(self, system: str, user: str) -> str:
        raise AssertionError("LLM should not be called for deterministic test-first cases")


def test_v24_resolves_suite_repair_without_llm(tmp_path: Path):
    case = load_case(REPO_ROOT / "benchmark" / "case_001")
    result = verify_case_v24(
        case,
        FailIfCalledLLM(),
        artifacts_root=tmp_path,
        timeout_seconds=10,
        run_id="v24-suite-repaired",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert result.test_delta.classification == "suite_repaired"
    assert result.investigator_called is False
    assert result.verifier_called is False
    assert result.reproduction_attempts == ()


def test_v24_resolves_partial_progress_without_llm(tmp_path: Path):
    case = load_case(REPO_ROOT / "benchmark" / "case_002")
    result = verify_case_v24(
        case,
        FailIfCalledLLM(),
        artifacts_root=tmp_path,
        timeout_seconds=10,
        run_id="v24-partial",
    )

    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.test_delta.classification == "partial_progress"
    assert result.investigator_called is False
    assert result.verifier_called is False


def test_v24_resolves_unreproduced_both_pass_as_inconclusive_without_llm(tmp_path: Path):
    case = load_case(REPO_ROOT / "benchmark" / "case_010")
    result = verify_case_v24(
        case,
        FailIfCalledLLM(),
        artifacts_root=tmp_path,
        timeout_seconds=10,
        run_id="v24-both-pass",
    )

    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.test_delta.classification == "both_pass"
    assert result.investigator_called is False
    assert result.verifier_called is False
