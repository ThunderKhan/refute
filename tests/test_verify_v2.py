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


def _valid_repro_payload() -> str:
    return json.dumps(
        {
            "rationale": "Exercise the reported lower-boundary failure.",
            "test_code": "from app import clamp_percentage\n\ndef test_zero_is_valid():\n    assert clamp_percentage(0) == 0\n",
        }
    )


def _verifier_payload() -> str:
    return json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The generated reproduction fails on the original and passes on the patch, while the patched existing suite passes.",
        }
    )


def test_verify_v2_retries_until_original_bug_reproduces(tmp_path: Path):
    first_repro = json.dumps(
        {
            "rationale": "A deliberately weak first attempt.",
            "test_code": "def test_noop():\n    assert True\n",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        first_repro,
        _valid_repro_payload(),
        _verifier_payload(),
    ])
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
    assert result.generation_failures == ()
    assert len(llm.calls) == 4

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "advanced_iteration_2"
    assert manifest["successful_reproduction"] is True
    assert manifest["capabilities"]["bounded_reproduction_retry"] is True
    assert manifest["capabilities"]["generation_failure_recovery"] is True
    assert manifest["capabilities"]["deterministic_verdict_gate"] is True
    assert manifest["capabilities"]["challenger"] is False

    evidence = (result.run_root / "evidence.jsonl").read_text(encoding="utf-8")
    assert "generated_test" in evidence
    assert "NOT_REPRODUCED" in evidence
    assert "REPRODUCED" in evidence


def test_verify_v2_recovers_from_malformed_generation(tmp_path: Path):
    malformed = "I think the test should target zero. Here is Python: assert clamp_percentage(0) == 0"
    llm = SequencedLLM([
        _investigator_payload(),
        malformed,
        _valid_repro_payload(),
        _verifier_payload(),
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v2(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        run_id="test-v2-malformed",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert result.generation_failures == ("reproducer did not return valid JSON",)
    assert len(result.reproduction_attempts) == 1
    assert result.successful_reproduction is result.reproduction_attempts[0]
    assert len(llm.calls) == 4

    evidence = (result.run_root / "evidence.jsonl").read_text(encoding="utf-8")
    assert "was unusable" in evidence
    assert malformed in (result.run_root / "reproduction_attempted" / "ev_0003.txt").read_text(encoding="utf-8")


def test_verify_v2_continues_when_all_generations_are_malformed(tmp_path: Path):
    malformed = "not json"
    verifier = json.dumps(
        {
            "verdict": "inconclusive",
            "reason": "Existing tests provide evidence, but no usable generated reproduction was produced.",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        malformed,
        malformed,
        malformed,
        verifier,
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v2(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        run_id="test-v2-all-malformed",
    )

    assert result.verdict is Verdict.INCONCLUSIVE
    assert len(result.generation_failures) == 3
    assert result.reproduction_attempts == ()
    assert result.successful_reproduction is None
    assert len(llm.calls) == 5

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["reproduction_generation_failures"] == 3
    assert manifest["successful_reproduction"] is False


def test_verify_v2_gate_rejects_complete_fix_when_repro_still_fails_on_patch(tmp_path: Path):
    conflicting_repro = json.dumps(
        {
            "rationale": "A candidate that fails on both versions.",
            "test_code": "from app import clamp_percentage\n\ndef test_zero_value():\n    assert clamp_percentage(0) == 999\n",
        }
    )
    misleading_verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The patch fixes the issue.",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        conflicting_repro,
        misleading_verifier,
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v2(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=1,
        run_id="test-v2-gate",
    )

    assert result.successful_reproduction is not None
    assert result.successful_reproduction.fixed_by_patch is False
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "Deterministic evidence gate rejected" in result.reason

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["model_proposed_verdict"] == "complete_fix"
    assert manifest["verdict"] == "inconclusive"
    assert manifest["evidence_gate_overrode_model"] is True
    assert manifest["complete_fix_forbidden_reasons"]
