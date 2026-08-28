import pytest

from refute.evidence import EvidenceKind, EvidenceRecord
from refute.orchestrator import RunStage, VerificationRun


def test_run_advances_through_valid_stages():
    run = VerificationRun("run_001", "case_001")

    run.advance(RunStage.INVESTIGATED)
    run.advance(RunStage.REPRODUCTION_ATTEMPTED)
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.advance(RunStage.PATCH_VERIFIED)
    run.advance(RunStage.REGRESSION_CHECKED)
    run.advance(RunStage.VERDICT_READY)
    run.advance(RunStage.COMPLETE)

    assert run.stage is RunStage.COMPLETE
    assert run.events[0] == "loaded"
    assert run.events[-1] == "complete"


def test_run_rejects_invalid_transition():
    run = VerificationRun("run_001", "case_001")

    with pytest.raises(ValueError, match="invalid run transition"):
        run.advance(RunStage.PATCH_VERIFIED)


def test_run_rejects_evidence_from_another_run():
    run = VerificationRun("run_001", "case_001")
    record = EvidenceRecord(
        evidence_id="ev_0001",
        run_id="run_999",
        case_id="case_001",
        stage="investigation",
        kind=EvidenceKind.OBSERVATION,
        summary="wrong run",
    )

    with pytest.raises(ValueError, match="different verification run"):
        run.attach(record)
