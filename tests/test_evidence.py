import json
from pathlib import Path

from refute.evidence import EvidenceKind, EvidenceStore


def test_evidence_store_persists_artifact_and_jsonl_index(tmp_path: Path):
    store = EvidenceStore(tmp_path, "run_001", "case_001")

    record = store.record(
        stage="reproduction",
        kind=EvidenceKind.TEST_RESULT,
        summary="candidate reproduction failed on original",
        content="1 failed\n",
        metadata={"exit_code": 1},
    )

    assert record.evidence_id == "ev_0001"
    assert record.artifact_path is not None
    assert record.artifact_path.read_text(encoding="utf-8") == "1 failed\n"

    lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["case_id"] == "case_001"
    assert payload["kind"] == "test_result"
    assert payload["metadata"]["exit_code"] == 1
