from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence


class Verdict(str, Enum):
    COMPLETE_FIX = "complete_fix"
    PARTIAL_FIX = "partial_fix"
    INEFFECTIVE_FIX = "ineffective_fix"
    REGRESSION_INTRODUCED = "regression_introduced"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class VerificationCase:
    case_id: str
    root: Path
    issue_path: Path
    original_path: Path
    patched_path: Path
    test_command: tuple[str, ...]
    notes: str = ""
    # Legacy benchmark cases carry their oracle inline. Benchmark v2 deliberately
    # leaves this unset so the verification pipeline cannot access ground truth.
    expected_verdict: Verdict | None = None

    @property
    def issue_text(self) -> str:
        return self.issue_path.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    command: tuple[str, ...]
    cwd: Path
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return not self.timed_out and self.exit_code == 0


@dataclass(slots=True)
class InspectionResult:
    case: VerificationCase
    original: ExecutionResult
    patched: ExecutionResult
    evidence_paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BaselineResult:
    case_id: str
    verdict: Verdict
    reason: str
    raw_response: str
    prompt_path: Path
    response_path: Path
    result_path: Path


def normalize_command(parts: Sequence[str]) -> tuple[str, ...]:
    command = tuple(str(part) for part in parts)
    if not command:
        raise ValueError("test command must not be empty")
    return command
