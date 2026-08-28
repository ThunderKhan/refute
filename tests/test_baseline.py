from __future__ import annotations

import json
from pathlib import Path

from refute.baseline import build_baseline_prompt, parse_baseline_response, run_baseline
from refute.case import load_case
from refute.models import Verdict


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


def test_prompt_contains_issue_and_diff() -> None:
    case = load_case(Path("benchmark/case_001"))
    prompt = build_baseline_prompt(case)

    assert "ISSUE REPORT" in prompt
    assert "PATCH DIFF" in prompt
    assert "value <= 0" in prompt
    assert "value < 0" in prompt
    assert "expected verdict" not in prompt.lower()


def test_parse_baseline_response_accepts_json() -> None:
    verdict, reason = parse_baseline_response(
        '{"verdict":"partial_fix","reason":"The patch handles only one boundary."}'
    )

    assert verdict is Verdict.PARTIAL_FIX
    assert reason == "The patch handles only one boundary."


def test_run_baseline_persists_artifacts(tmp_path: Path) -> None:
    case = load_case(Path("benchmark/case_001"))
    llm = FakeLLM(
        '{"verdict":"complete_fix","reason":"The changed boundary check matches the issue."}'
    )

    result = run_baseline(case, llm, tmp_path)

    assert result.verdict is Verdict.COMPLETE_FIX
    assert len(llm.calls) == 1
    assert result.prompt_path.is_file()
    assert result.response_path.is_file()
    assert result.result_path.is_file()

    stored = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert stored["case_id"] == "case_001"
    assert stored["verdict"] == "complete_fix"


def test_parse_baseline_response_rejects_invalid_verdict() -> None:
    try:
        parse_baseline_response('{"verdict":"looks_good","reason":"Seems fine."}')
    except ValueError as exc:
        assert "baseline verdict must be one of" in str(exc)
    else:
        raise AssertionError("invalid verdict should fail")
