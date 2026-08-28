import sys
from pathlib import Path

from refute.executor import run_command


def test_run_command_captures_success(tmp_path: Path):
    result = run_command(
        (sys.executable, "-c", "print('ok')"),
        tmp_path,
        timeout_seconds=2,
    )

    assert result.passed
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"
    assert not result.timed_out


def test_run_command_captures_failure(tmp_path: Path):
    result = run_command(
        (sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"),
        tmp_path,
        timeout_seconds=2,
    )

    assert not result.passed
    assert result.exit_code == 3
    assert result.stdout.strip() == "bad"


def test_run_command_marks_timeout(tmp_path: Path):
    result = run_command(
        (sys.executable, "-c", "import time; time.sleep(2)"),
        tmp_path,
        timeout_seconds=0.05,
    )

    assert result.timed_out
    assert result.exit_code is None
