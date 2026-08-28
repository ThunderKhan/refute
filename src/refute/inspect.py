from __future__ import annotations

from pathlib import Path

from .executor import DEFAULT_TIMEOUT_SECONDS, run_command
from .models import ExecutionResult, InspectionResult, VerificationCase


def _format_execution(label: str, result: ExecutionResult) -> str:
    command = " ".join(result.command)
    status = "TIMEOUT" if result.timed_out else str(result.exit_code)
    return (
        f"{label}\n"
        f"cwd: {result.cwd}\n"
        f"command: {command}\n"
        f"exit_code: {status}\n"
        f"duration_seconds: {result.duration_seconds:.3f}\n"
        "\n--- stdout ---\n"
        f"{result.stdout}"
        "\n--- stderr ---\n"
        f"{result.stderr}"
    )


def inspect_case(
    case: VerificationCase,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> InspectionResult:
    original = run_command(case.test_command, case.original_path, timeout_seconds)
    patched = run_command(case.test_command, case.patched_path, timeout_seconds)

    evidence_dir = Path(artifacts_root).resolve() / case.case_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    original_path = evidence_dir / "original.txt"
    patched_path = evidence_dir / "patched.txt"
    original_path.write_text(_format_execution("original", original), encoding="utf-8")
    patched_path.write_text(_format_execution("patched", patched), encoding="utf-8")

    return InspectionResult(
        case=case,
        original=original,
        patched=patched,
        evidence_paths=[original_path, patched_path],
    )
