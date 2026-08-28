from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .models import ExecutionResult


DEFAULT_TIMEOUT_SECONDS = 20.0


def run_command(
    command: tuple[str, ...],
    cwd: str | Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ExecutionResult:
    workdir = Path(cwd).resolve()
    started = time.perf_counter()

    try:
        completed = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - started
        return ExecutionResult(
            command=command,
            cwd=workdir,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")

        return ExecutionResult(
            command=command,
            cwd=workdir,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=True,
        )
