from __future__ import annotations

import json
from pathlib import Path

from .models import Verdict, VerificationCase, normalize_command


class CaseFormatError(ValueError):
    """Raised when a benchmark case does not match the expected layout."""


def load_case(case_dir: str | Path) -> VerificationCase:
    root = Path(case_dir).resolve()
    if not root.is_dir():
        raise CaseFormatError(f"case directory does not exist: {root}")

    issue_path = root / "issue.md"
    original_path = root / "original"
    patched_path = root / "patched"
    expected_path = root / "expected.json"

    for required in (issue_path, expected_path):
        if not required.is_file():
            raise CaseFormatError(f"missing required file: {required}")

    for required_dir in (original_path, patched_path):
        if not required_dir.is_dir():
            raise CaseFormatError(f"missing required directory: {required_dir}")

    try:
        metadata = json.loads(expected_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaseFormatError(f"invalid JSON in {expected_path}: {exc}") from exc

    case_id = metadata.get("case_id", root.name)
    verdict_raw = metadata.get("expected_verdict")
    test_command_raw = metadata.get("test_command", ["python", "-m", "pytest", "-q"])

    if not isinstance(case_id, str) or not case_id.strip():
        raise CaseFormatError("case_id must be a non-empty string")

    try:
        expected_verdict = Verdict(verdict_raw)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(v.value for v in Verdict)
        raise CaseFormatError(
            f"expected_verdict must be one of: {allowed}"
        ) from exc

    if not isinstance(test_command_raw, list) or not all(
        isinstance(part, str) for part in test_command_raw
    ):
        raise CaseFormatError("test_command must be a JSON array of strings")

    notes = metadata.get("notes", "")
    if not isinstance(notes, str):
        raise CaseFormatError("notes must be a string")

    return VerificationCase(
        case_id=case_id.strip(),
        root=root,
        issue_path=issue_path,
        original_path=original_path,
        patched_path=patched_path,
        expected_verdict=expected_verdict,
        test_command=normalize_command(test_command_raw),
        notes=notes,
    )
