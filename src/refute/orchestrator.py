from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .evidence import EvidenceRecord


class RunStage(str, Enum):
    LOADED = "loaded"
    INVESTIGATED = "investigated"
    REPRODUCTION_ATTEMPTED = "reproduction_attempted"
    ORIGINAL_VERIFIED = "original_verified"
    PATCH_VERIFIED = "patch_verified"
    CHALLENGED = "challenged"
    REGRESSION_CHECKED = "regression_checked"
    VERDICT_READY = "verdict_ready"
    COMPLETE = "complete"


_ALLOWED_TRANSITIONS: dict[RunStage, set[RunStage]] = {
    RunStage.LOADED: {RunStage.INVESTIGATED},
    # Iteration 1 intentionally skips generated reproduction. Later iterations can
    # take the reproduction branch without changing the run model.
    RunStage.INVESTIGATED: {RunStage.REPRODUCTION_ATTEMPTED, RunStage.ORIGINAL_VERIFIED},
    RunStage.REPRODUCTION_ATTEMPTED: {RunStage.ORIGINAL_VERIFIED},
    RunStage.ORIGINAL_VERIFIED: {RunStage.PATCH_VERIFIED},
    RunStage.PATCH_VERIFIED: {RunStage.CHALLENGED, RunStage.REGRESSION_CHECKED},
    RunStage.CHALLENGED: {RunStage.REGRESSION_CHECKED},
    RunStage.REGRESSION_CHECKED: {RunStage.VERDICT_READY},
    RunStage.VERDICT_READY: {RunStage.COMPLETE},
    RunStage.COMPLETE: set(),
}


@dataclass(slots=True)
class VerificationRun:
    run_id: str
    case_id: str
    stage: RunStage = RunStage.LOADED
    evidence: list[EvidenceRecord] = field(default_factory=list)
    events: list[str] = field(default_factory=lambda: [RunStage.LOADED.value])

    def advance(self, next_stage: RunStage) -> None:
        if next_stage not in _ALLOWED_TRANSITIONS[self.stage]:
            raise ValueError(
                f"invalid run transition: {self.stage.value} -> {next_stage.value}"
            )
        self.stage = next_stage
        self.events.append(next_stage.value)

    def attach(self, record: EvidenceRecord) -> None:
        if record.run_id != self.run_id or record.case_id != self.case_id:
            raise ValueError("evidence belongs to a different verification run")
        self.evidence.append(record)
