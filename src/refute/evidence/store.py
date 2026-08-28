from __future__ import annotations

import json
from pathlib import Path

from .models import EvidenceKind, EvidenceRecord


class EvidenceStore:
    """Persist run evidence and an append-only JSONL provenance index."""

    def __init__(self, root: str | Path, run_id: str, case_id: str):
        self.root = Path(root).resolve() / "runs" / run_id
        self.run_id = run_id
        self.case_id = case_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "evidence.jsonl"
        self._counter = 0

    def record(
        self,
        *,
        stage: str,
        kind: EvidenceKind,
        summary: str,
        content: str | None = None,
        suffix: str = ".txt",
        metadata: dict | None = None,
    ) -> EvidenceRecord:
        self._counter += 1
        evidence_id = f"ev_{self._counter:04d}"
        artifact_path: Path | None = None
        if content is not None:
            stage_dir = self.root / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = stage_dir / f"{evidence_id}{suffix}"
            artifact_path.write_text(content, encoding="utf-8")

        record = EvidenceRecord(
            evidence_id=evidence_id,
            run_id=self.run_id,
            case_id=self.case_id,
            stage=stage,
            kind=kind,
            summary=summary,
            artifact_path=artifact_path,
            metadata=metadata,
        )
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        return record
