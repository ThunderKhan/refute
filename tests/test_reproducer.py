import json

import pytest

from refute.agents.reproducer import parse_reproduction, validate_generated_test


def test_parse_reproduction_accepts_focused_pytest_source():
    raw = json.dumps(
        {
            "rationale": "Exercise the lower boundary reported by the issue.",
            "test_code": "from app import clamp_percentage\n\ndef test_zero():\n    assert clamp_percentage(0) == 0\n",
        }
    )

    candidate = parse_reproduction(raw, attempt=1)

    assert candidate.attempt == 1
    assert "clamp_percentage(0)" in candidate.test_code


def test_generated_reproduction_rejects_subprocess_import():
    with pytest.raises(ValueError, match="blocked module"):
        validate_generated_test("import subprocess\n\ndef test_x():\n    assert True\n")


def test_generated_reproduction_rejects_open_call():
    with pytest.raises(ValueError, match="blocked call"):
        validate_generated_test("def test_x():\n    open('x.txt', 'w')\n")
