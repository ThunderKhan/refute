import json

import pytest

from refute.agents.challenger import parse_challenges


def test_parse_challenges_accepts_multiple_focused_tests():
    raw = json.dumps(
        {
            "candidates": [
                {
                    "rationale": "upper boundary may still be rejected",
                    "test_code": "from app import normalize_percentage\n\ndef test_upper():\n    assert normalize_percentage(100) == 100\n",
                },
                {
                    "rationale": "nearby interior value should remain valid",
                    "test_code": "from app import normalize_percentage\n\ndef test_interior():\n    assert normalize_percentage(99) == 99\n",
                },
            ]
        }
    )

    plan = parse_challenges(raw)

    assert len(plan.candidates) == 2
    assert plan.candidates[0].index == 1
    assert "100" in plan.candidates[0].test_code


def test_parse_challenges_reuses_generated_test_safety_policy():
    raw = json.dumps(
        {
            "candidates": [
                {
                    "rationale": "unsafe",
                    "test_code": "import subprocess\n\ndef test_bad():\n    subprocess.run(['echo', 'x'])\n",
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="blocked module"):
        parse_challenges(raw)
