from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify import verify_case


REPO_ROOT = Path(__file__).resolve().parents[1]


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def test_verify_case_runs_investigator_execution_and_verifier(tmp_path: Path):
    investigator = json.dumps(
        {
            "expected_behavior": "0 through 100 inclusive are valid",
            "reported_failure": "0 is rejected",
            "trigger_conditions": ["value equals 0"],
            "likely_files": ["app.py"],
            "reproduction_strategy": "call clamp_percentage(0)",
            "risk_areas": ["lower boundary", "upper boundary"],
        }
    )
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "Original tests fail and patched tests pass for the supplied suite.",
        }
    )
    llm = SequencedLLM([investigator, verifier])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        run_id="test-run",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert result.original.passed is False
    assert result.patched.passed is True
    assert len(llm.calls) == 2
    assert (result.run_root / "evidence.jsonl").is_file()
    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["capabilities"]["investigator"] is True
    assert manifest["capabilities"]["generated_reproduction"] is False
    assert manifest["capabilities"]["challenger"] is False
