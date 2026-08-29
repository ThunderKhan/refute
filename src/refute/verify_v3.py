from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.challenger import ChallengeGenerationError, ChallengePlan, generate_challenges
from .agents.investigator import Investigation
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun
from .verify_v2 import _execution_text, _investigate_with_retry, _run_generated_test
from .verify_v23 import TestDelta, analyze_test_delta
from .verify_v24 import _triage_delta


@dataclass(frozen=True, slots=True)
class ChallengeExecution:
    index: int
    rationale: str
    test_code: str
    original: ExecutionResult
    patched: ExecutionResult
    classification: str

    @property
    def is_counterexample(self) -> bool:
        return self.classification in {"regression_counterexample", "remaining_bug_counterexample"}


@dataclass(frozen=True, slots=True)
class VerificationResultV3:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    investigation: Investigation | None
    challenge_plan: ChallengePlan | None
    challenge_executions: tuple[ChallengeExecution, ...]
    challenger_called: bool
    investigator_called: bool
    verifier_called: bool
    run_root: Path


def _classify_challenge(original: ExecutionResult, patched: ExecutionResult) -> str:
    if original.timed_out or patched.timed_out:
        return "invalid_execution"
    # Pytest exit 0 = pass, exit 1 = test assertion/failure. Collection, usage,
    # internal, and environment errors (2+) are not semantic patch evidence.
    if original.exit_code not in {0, 1} or patched.exit_code not in {0, 1}:
        return "invalid_execution"
    if patched.exit_code == 0:
        return "survived"
    if original.exit_code == 0 and patched.exit_code == 1:
        return "regression_counterexample"
    if original.exit_code == 1 and patched.exit_code == 1:
        return "remaining_bug_counterexample"
    return "invalid_execution"


def _challenge_verdict(executions: list[ChallengeExecution]) -> tuple[Verdict | None, str | None]:
    regressions = [item for item in executions if item.classification == "regression_counterexample"]
    if regressions:
        return (
            Verdict.REGRESSION_INTRODUCED,
            "Challenger found a nearby case that passes on the original but fails on the patch, providing executable regression evidence.",
        )

    remaining = [item for item in executions if item.classification == "remaining_bug_counterexample"]
    if remaining:
        return (
            Verdict.PARTIAL_FIX,
            "Challenger found nearby issue-grounded behavior that fails on both the original and the patch after the reported trigger was repaired.",
        )

    return None, None


def verify_case_v3(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV3:
    if max_provider_attempts < 1:
        raise ValueError("max_provider_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="verification case loaded; benchmark oracle and hidden tests withheld from agents",
        metadata={"iteration": "3", "routing": "test_first_then_challenge"},
    ))

    original = run_command(case.test_command, case.original_path, timeout_seconds)
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.attach(store.record(
        stage=RunStage.ORIGINAL_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"public tests on original: {'PASS' if original.passed else 'FAIL'}",
        content=_execution_text("ORIGINAL PUBLIC TESTS", original),
        metadata={"passed": original.passed, "exit_code": original.exit_code, "timed_out": original.timed_out},
    ))

    patched = run_command(case.test_command, case.patched_path, timeout_seconds)
    run.advance(RunStage.PATCH_VERIFIED)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"public tests on patch: {'PASS' if patched.passed else 'FAIL'}",
        content=_execution_text("PATCHED PUBLIC TESTS", patched),
        metadata={"passed": patched.passed, "exit_code": patched.exit_code, "timed_out": patched.timed_out},
    ))

    delta = analyze_test_delta(original, patched)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.OBSERVATION,
        summary=f"public test delta: {delta.classification}",
        content=json.dumps({
            "fixed_tests": delta.fixed_tests,
            "remaining_failures": delta.remaining_failures,
            "new_failures": delta.new_failures,
            "classification": delta.classification,
            "reason": delta.reason,
        }, indent=2) + "\n",
        suffix=".json",
    ))

    immediate_verdict, immediate_reason = _triage_delta(delta)
    if delta.classification == "suite_repaired":
        immediate_verdict = None
        immediate_reason = None

    investigation: Investigation | None = None
    challenge_plan: ChallengePlan | None = None
    challenge_executions: list[ChallengeExecution] = []
    investigator_called = False
    challenger_called = False
    verifier_called = False

    if immediate_verdict is not None:
        verdict = immediate_verdict
        reason = immediate_reason or "Deterministic test-first triage resolved the case."
        run.advance(RunStage.REGRESSION_CHECKED)
    elif delta.classification == "suite_repaired" and delta.fixed_tests:
        investigator_called = True
        investigation = _investigate_with_retry(
            case, llm, store, run, max_attempts=max_provider_attempts
        )
        run.advance(RunStage.INVESTIGATED)
        run.attach(store.record(
            stage=RunStage.INVESTIGATED.value,
            kind=EvidenceKind.MODEL_RESPONSE,
            summary="Investigator framed nearby falsification risks after public suite repair",
            content=json.dumps(investigation.to_dict(), indent=2) + "\n",
            suffix=".json",
        ))

        challenger_called = True
        try:
            challenge_plan = generate_challenges(case, investigation, llm)
        except ChallengeGenerationError as exc:
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.MODEL_RESPONSE,
                summary=f"Challenger output unusable: {exc}",
                content=exc.raw_response,
                suffix=".txt",
                metadata={"usable": False, "error": str(exc)},
            ))
            challenge_plan = None
        except LLMError as exc:
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Challenger provider failure: {exc}",
                metadata={"provider_error": True, "error": str(exc)},
            ))
            challenge_plan = None

        if challenge_plan is not None:
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.MODEL_RESPONSE,
                summary=f"Challenger proposed {len(challenge_plan.candidates)} nearby falsification case(s)",
                content=challenge_plan.raw_response,
                suffix=".json",
                metadata={"candidate_count": len(challenge_plan.candidates)},
            ))
            for candidate in challenge_plan.candidates:
                original_challenge = _run_generated_test(
                    candidate.test_code, case.original_path, timeout_seconds
                )
                patched_challenge = _run_generated_test(
                    candidate.test_code, case.patched_path, timeout_seconds
                )
                classification = _classify_challenge(original_challenge, patched_challenge)
                execution = ChallengeExecution(
                    index=candidate.index,
                    rationale=candidate.rationale,
                    test_code=candidate.test_code,
                    original=original_challenge,
                    patched=patched_challenge,
                    classification=classification,
                )
                challenge_executions.append(execution)
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.TEST_RESULT,
                    summary=f"challenge {candidate.index}: {classification}",
                    content=(
                        _execution_text(f"CHALLENGE {candidate.index} / ORIGINAL", original_challenge)
                        + "\n"
                        + _execution_text(f"CHALLENGE {candidate.index} / PATCHED", patched_challenge)
                    ),
                    metadata={
                        "candidate": candidate.index,
                        "classification": classification,
                        "rationale": candidate.rationale,
                    },
                ))

        run.advance(RunStage.CHALLENGED)
        verdict, reason = _challenge_verdict(challenge_executions)
        if verdict is None:
            valid = [item for item in challenge_executions if item.classification != "invalid_execution"]
            if valid and all(item.classification == "survived" for item in valid):
                verdict = Verdict.COMPLETE_FIX
                reason = (
                    "The public reported trigger is repaired and the patch survived all valid Challenger-generated nearby cases within the bounded challenge budget."
                )
            else:
                verdict = Verdict.INCONCLUSIVE
                reason = (
                    "The public trigger is repaired, but the Challenger produced no valid decisive counterexample evidence; patch completeness remains inconclusive."
                )
        run.advance(RunStage.REGRESSION_CHECKED)
    else:
        verdict = Verdict.INCONCLUSIVE
        reason = (
            "Public deterministic evidence did not establish a repaired reported trigger, so nearby falsification would not support a causal patch verdict."
        )
        run.advance(RunStage.REGRESSION_CHECKED)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 3 conditionally challenges patches that appear fixed on public evidence",
        metadata={
            "investigator_called": investigator_called,
            "challenger_called": challenger_called,
            "challenge_candidates": len(challenge_executions),
            "challenge_counterexamples": sum(item.is_counterexample for item in challenge_executions),
            "verifier_called": verifier_called,
            "hidden_tests_used": False,
            "oracle_used": False,
        },
    ))

    run.advance(RunStage.VERDICT_READY)
    raw_verdict = json.dumps({"verdict": verdict.value, "reason": reason})
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 3 verdict: {verdict.value}",
        content=raw_verdict,
        metadata={"final_verdict": verdict.value, "reason": reason},
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_3",
        "iteration": "3",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": {
            "classification": delta.classification,
            "fixed_tests": list(delta.fixed_tests),
            "remaining_failures": list(delta.remaining_failures),
            "new_failures": list(delta.new_failures),
        },
        "investigator_called": investigator_called,
        "challenger_called": challenger_called,
        "challenge_candidates": len(challenge_executions),
        "challenge_counterexamples": sum(item.is_counterexample for item in challenge_executions),
        "challenge_classifications": [item.classification for item in challenge_executions],
        "verifier_called": verifier_called,
        "capabilities": {
            "test_first_routing": True,
            "existing_test_execution": True,
            "test_delta_engine": True,
            "conditional_investigator": True,
            "challenger": True,
            "bounded_nearby_falsification": True,
            "deterministic_challenge_execution": True,
            "oracle_visible_to_agents": False,
            "hidden_tests_visible_to_agents": False,
        },
    }
    (store.root / "result.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return VerificationResultV3(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        original=original,
        patched=patched,
        test_delta=delta,
        investigation=investigation,
        challenge_plan=challenge_plan,
        challenge_executions=tuple(challenge_executions),
        challenger_called=challenger_called,
        investigator_called=investigator_called,
        verifier_called=verifier_called,
        run_root=store.root,
    )
