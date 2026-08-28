from __future__ import annotations

import json
from pathlib import Path

from refute.case import load_case
from refute.models import Verdict
from refute.verify_v22 import verify_case_v22


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


def _bad_repro(value: int = 50) -> str:
    return json.dumps(
        {
            "rationale": "Intentionally wrong assertion that fails on both versions.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_wrong_expectation():\n"
                f"    assert clamp_percentage({value}) == 999\n"
            ),
        }
    )


def _good_repro() -> str:
    return json.dumps(
        {
            "rationale": "Exercise the reported lower-boundary failure.",
            "test_code": (
                "from app import clamp_percentage\n\n"
                "def test_zero_is_valid():\n"
                "    assert clamp_percentage(0) == 0\n"
            ),
        }
    )


def test_v22_blocks_negative_verdict_from_diagnostic_only_reproduction(tmp_path: Path):
    verifier = json.dumps(
        {
            "verdict": "ineffective_fix",
            "reason": "The generated test failed on both versions.",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        _bad_repro(50),
        verifier,
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v22(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=1,
        run_id="v22-weighted-gate",
    )

    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.discriminating_reproduction is None
    assert result.reproduction_attempts[0].classification == "non_discriminating"
    assert result.reproduction_attempts[0].evidence_weight == "diagnostic"

    manifest = json.loads((result.run_root / "result.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "advanced_iteration_2_2"
    assert manifest["evidence_gate_overrode_model"] is True
    assert "ineffective_fix" in manifest["forbidden_verdicts"]
    assert manifest["capabilities"]["evidence_weighting"] is True


def test_v22_stops_after_repeated_non_discriminating_attempts(tmp_path: Path):
    verifier = json.dumps(
        {
            "verdict": "inconclusive",
            "reason": "No high-confidence reproduction was established.",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        _bad_repro(50),
        _bad_repro(25),
        verifier,
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v22(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        stagnation_limit=2,
        run_id="v22-stagnation",
    )

    assert len(result.reproduction_attempts) == 2
    assert result.stopped_for_stagnation is True
    assert all(item.classification == "non_discriminating" for item in result.reproduction_attempts)
    assert len(llm.calls) == 4

    evidence = (result.run_root / "evidence.jsonl").read_text(encoding="utf-8")
    assert "stopped early" in evidence


def test_v22_keeps_discriminating_reproduction_high_confidence(tmp_path: Path):
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The discriminating reproduction fails on the original and passes on the patch.",
        }
    )
    llm = SequencedLLM([
        _investigator_payload(),
        _good_repro(),
        verifier,
    ])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v22(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=3,
        run_id="v22-discriminating",
    )

    assert result.verdict is Verdict.COMPLETE_FIX
    assert result.discriminating_reproduction is result.reproduction_attempts[0]
    assert result.reproduction_attempts[0].classification == "discriminating"
    assert result.reproduction_attempts[0].evidence_weight == "high"
    assert result.stopped_for_stagnation is False


def test_v22_labels_original_pass_as_not_reproduced(tmp_path: Path):
    no_op = json.dumps(
        {
            "rationale": "Does not reproduce the issue.",
            "test_code": "def test_noop():\n    assert True\n",
        }
    )
    verifier = json.dumps(
        {
            "verdict": "complete_fix",
            "reason": "The patched deterministic suite passes; the generated attempt did not reproduce anything.",
        }
    )
    llm = SequencedLLM([_investigator_payload(), no_op, verifier])
    case = load_case(REPO_ROOT / "benchmark" / "case_001")

    result = verify_case_v22(
        case,
        llm,
        artifacts_root=tmp_path,
        timeout_seconds=10,
        max_reproduction_attempts=1,
        run_id="v22-not-reproduced",
    )

    assert result.reproduction_attempts[0].classification == "not_reproduced"
    assert result.reproduction_attempts[0].evidence_weight == "none"
    assert result.verdict is Verdict.COMPLETE_FIX
