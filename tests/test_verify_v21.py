from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify_v21 import verify_case_v21


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


def _investigator_payload() -> str:
    return json.dumps(
        {
            "expected_behavior": "0 through 100 inclusive are valid",
            "reported_failure": "0 is rejected",
            "trigger_conditions": ["value equals 0"],
            "likely_files": ["app.py"],
            "reproduction_strategy": "call clamp_percentage(0)",
            "risk_areas": ["lower boundary", "upper boundary"],
        }
    )


def _bad_both_fail_repro() -> str:
    return json.dumps(
        {
            "rationale": "This assertion is intentionally wrong on both versions.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_wrong_expectation():\n"
                "    assert clamp_percentage(50) == 999\n"
            ),
        }
    )


def _good_discriminating_repro() -> str:
    return json.dumps(
        {
            "rationale": "Exercise the reported zero boundary bug.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_zero_is_valid():\n"
                "    assert clamp_percentage(0) == 0\n"
            ),
        }
    )


def test_v21_retries_when_generated_test_fails_on_both_versions(tmp_path: Path):
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "A discriminating reproduction was found and the patched existing suite passes.",
        }
    )
    llm = SequencedLLM(
        [
            _investigator_payload(),
            _bad_both_fail_repro(),
            _good_discriminating_repro(),
            verifier,
        ]
    )
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v21(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        run_id="v21-discrimination",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert len(result.reproduction_attempts) == 2
    first = result.reproduction_attempts[0]
    assert first.original_failed is True
    assert first.patch_passed is False
    assert first.discriminating is False
    assert result.discriminating_reproduction is result.reproduction_attempts[1]
    assert result.discriminating_reproduction.discriminating is True
    assert len(llm.calls) == 4

    # The retry prompt must include evidence from both versions, not just original.
    second_reproducer_prompt = llm.calls[2][1]
    assert "failed on BOTH the original and the patch" in second_reproducer_prompt
    assert "PRIOR ORIGINAL REPRODUCTION RUN" in second_reproducer_prompt
    assert "PRIOR PATCHED REPRODUCTION RUN" in second_reproducer_prompt

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "advanced_iteration_2_1"
    assert manifest["discriminating_reproduction_found"] is True
    assert manifest["capabilities"]["discriminating_reproduction_semantics"] is True


def test_v21_does_not_call_both_fail_attempt_successful(tmp_path: Path):
    second_bad = json.dumps(
        {
            "rationale": "Another non-discriminating wrong assertion.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_another_wrong_expectation():\n"
                "    assert clamp_percentage(25) == -1\n"
            ),
        }
    )
    verifier = json.dumps(
        {
            "verdict": "inconclusive",
            "reason": "No generated test discriminated original from patch.",
        }
    )
    llm = SequencedLLM(
        [
            _investigator_payload(),
            _bad_both_fail_repro(),
            second_bad,
            verifier,
        ]
    )
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v21(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=2,
        run_id="v21-no-discrimination",
    )

    assert result.verdict is Verdict.INCONCLUSIVE
    assert len(result.reproduction_attempts) == 2
    assert all(not attempt.discriminating for attempt in result.reproduction_attempts)
    assert result.discriminating_reproduction is None

    evidence = (result.run_root / "evidence.jsonl").read_text(encoding="utf-8")
    assert "NON_DISCRIMINATING" in evidence
    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["discriminating_reproduction_found"] is False
