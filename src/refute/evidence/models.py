from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class EvidenceKind(str, Enum):
    PROMPT = "prompt"
    MODEL_RESPONSE = "model_response"
    COMMAND = "command"
    TEST_RESULT = "test_result"
    GENERATED_TEST = "generated_test"
    OBSERVATION = "observation"
    VERDICT = "verdict"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    run_id: str
    case_id: str
    stage: str
    kind: EvidenceKind
    summary: str
    artifact_path: Path | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["artifact_path"] = (
            str(self.artifact_path) if self.artifact_path is not None else None
        )
        return payload
