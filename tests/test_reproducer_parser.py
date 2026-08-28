import json

from refute.agents.reproducer import parse_reproduction


def test_parse_reproduction_accepts_reasoning_before_json():
    payload = json.dumps(
        {
            "rationale": "exercise the lower boundary",
            "test_code": "from app import clamp_percentage\n\ndef test_zero():\n    assert clamp_percentage(0) == 0\n",
        }
    )
    raw = "<think>Need a focused boundary test.</think>\n" + payload

    result = parse_reproduction(raw, attempt=1)

    assert result.rationale == "exercise the lower boundary"
    assert "clamp_percentage(0)" in result.test_code


def test_parse_reproduction_accepts_markdown_wrapped_json():
    payload = json.dumps(
        {
            "rationale": "exercise the lower boundary",
            "test_code": "from app import clamp_percentage\n\ndef test_zero():\n    assert clamp_percentage(0) == 0\n",
        }
    )
    raw = "Here is the requested object:\n```json\n" + payload + "\n```"

    result = parse_reproduction(raw, attempt=2)

    assert result.attempt == 2
    assert result.test_code.endswith("\n")
