from __future__ import annotations

import json
from pathlib import Path

from .models import Verdict, VerificationCase, normalize_command


class CaseFormatError(ValueError):
    """Raised when a benchmark case does not match the expected layout."""


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaseFormatError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CaseFormatError(f"JSON root must be an object: {path}")
    return payload


def load_case(case_dir: str | Path) -> VerificationCase:
    root = Path(case_dir).resolve()
    if not root.is_dir():
        raise CaseFormatError(f"case directory does not exist: {root}")

    issue_path = root / "issue.md"
    original_path = root / "original"
    patched_path = root / "patched"
    public_metadata_path = root / "case.json"
    legacy_metadata_path = root / "expected.json"

    if public_metadata_path.is_file():
        metadata_path = public_metadata_path
        oracle_is_inline = False
    elif legacy_metadata_path.is_file():
        metadata_path = legacy_metadata_path
        oracle_is_inline = True
    else:
        raise CaseFormatError(
            f"missing required file: expected {public_metadata_path.name} or {legacy_metadata_path.name}"
        )

    if not issue_path.is_file():
        raise CaseFormatError(f"missing required file: {issue_path}")
    for required_dir in (original_path, patched_path):
        if not required_dir.is_dir():
            raise CaseFormatError(f"missing required directory: {required_dir}")

    metadata = _read_json(metadata_path)
    case_id = metadata.get("case_id", root.name)
    test_command_raw = metadata.get("test_command", ["python", "-m", "pytest", "-q"])

    if not isinstance(case_id, str) or not case_id.strip():
        raise CaseFormatError("case_id must be a non-empty string")
    if not isinstance(test_command_raw, list) or not all(
        isinstance(part, str) for part in test_command_raw
    ):
        raise CaseFormatError("test_command must be a JSON array of strings")

    notes = metadata.get("notes", "")
    if not isinstance(notes, str):
        raise CaseFormatError("notes must be a string")

    expected_verdict: Verdict | None = None
    if oracle_is_inline:
        verdict_raw = metadata.get("expected_verdict")
        try:
            expected_verdict = Verdict(verdict_raw)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(v.value for v in Verdict)
            raise CaseFormatError(
                f"expected_verdict must be one of: {allowed}"
            ) from exc
    elif "expected_verdict" in metadata:
        raise CaseFormatError(
            "case.json must not contain expected_verdict; Benchmark v2 oracles belong outside the public case directory"
        )

    return VerificationCase(
        case_id=case_id.strip(),
        root=root,
        issue_path=issue_path,
        original_path=original_path,
        patched_path=patched_path,
        test_command=normalize_command(test_command_raw),
        notes=notes,
        expected_verdict=expected_verdict,
    )
