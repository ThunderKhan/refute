from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify_v2 import verify_case_v2


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


def test_verify_v2_retries_until_original_bug_reproduces(tmp_path: Path):
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
    first_repro = json.dumps(
        {
            "rationale": "A deliberately weak first attempt.",
            "test_code": "def test_noop():\n    assert True\n",
        }
    )
    second_repro = json.dumps(
        {
            "rationale": "Exercise the reported lower-boundary failure.",
            "test_code": "from app import clamp_percentage\n\ndef test_zero_is_valid():\n    assert clamp_percentage(0) == 0\n",
        }
    )
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The generated reproduction fails on the original and passes on the patch, while the patched existing suite passes.",
        }
    )
    llm = SequencedLLM([investigator, first_repro, second_repro, verifier])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v2(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        run_id="test-v2-run",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert len(result.reproduction_attempts) == 2
    assert result.reproduction_attempts[0].reproduced is False
    assert result.successful_reproduction is result.reproduction_attempts[1]
    assert result.successful_reproduction.fixed_by_patch is True
    assert len(llm.calls) == 4

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "advanced_iteration_2"
    assert manifest["successful_reproduction"] is True
    assert manifest["capabilities"]["bounded_reproduction_retry"] is True
    assert manifest["capabilities"]["challenger"] is False

    evidence = (result.run_root / "evidence.jsonl").read_text(encoding="utf-8")
    assert "generated_test" in evidence
    assert "NOT_REPRODUCED" in evidence
    assert "REPRODUCED" in evidence
