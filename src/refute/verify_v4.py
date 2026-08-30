from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.challenge_critic_v4 import critique_intent_v4
from .agents.challenger_v4 import (
    ChallengeIntentErrorV4,
    ChallengeIntentV4,
    compile_intent_to_pytest_v4,
    generate_challenge_intent_v4,
)
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun
from .verify_v2 import _execution_text, _run_generated_test
from .verify_v23 import TestDelta, analyze_test_delta
from .verify_v24 import _triage_delta


@dataclass(frozen=True, slots=True)
class ChallengeExecutionV4:
    intent: ChallengeIntentV4
    test_code: str
    original: ExecutionResult
    patched: ExecutionResult
    classification: str

    @property
    def is_counterexample(self) -> bool:
        return self.classification in {
            "regression_counterexample",
            "remaining_requirement_counterexample",
        }


@dataclass(frozen=True, slots=True)
class VerificationResultV4:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    challenge_executions: tuple[ChallengeExecutionV4, ...]
    challenge_generation_failures: tuple[str, ...]
    critic_failures: tuple[str, ...]
    critic_rejections: tuple[str, ...]
    investigator_called: bool
    challenger_called: bool
    critic_called: bool
    verifier_called: bool
    run_root: Path


def _classify(intent: ChallengeIntentV4, original: ExecutionResult, patched: ExecutionResult) -> str:
    if original.timed_out or patched.timed_out:
        return "invalid_execution"
    if original.exit_code not in {0, 1} or patched.exit_code not in {0, 1}:
        return "invalid_execution"
    if patched.passed:
        return "survived"
    if original.passed:
        return "regression_counterexample"
    if intent.kind == "remaining_requirement" and original.exit_code == 1 and patched.exit_code == 1:
        return "remaining_requirement_counterexample"
    return "non_decisive"


def _intent_fingerprint(intent: ChallengeIntentV4) -> str:
    return json.dumps(
        {
            "kind": intent.kind,
            "contract_id": intent.contract_id,
            "target": intent.target,
            "args": list(intent.args),
            "expectation_type": intent.expectation_type,
            "expected_value": intent.expected_value,
            "expected_exception": intent.expected_exception,
            "arg_index": intent.arg_index,
        },
        sort_keys=True,
    )


def verify_case_v4(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_challenge_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV4:
    if max_challenge_attempts < 1:
        raise ValueError("max_challenge_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="case loaded; Iteration 4 uses intent-first challenge generation with deterministic test synthesis",
        metadata={"iteration": "4", "oracle_used": False, "hidden_tests_used": False},
    ))

    original = run_command(case.test_command, case.original_path, timeout_seconds)
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.attach(store.record(
        stage=RunStage.ORIGINAL_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"public original tests: {'PASS' if original.passed else 'FAIL'}",
        content=_execution_text("ORIGINAL PUBLIC TESTS", original),
    ))

    patched = run_command(case.test_command, case.patched_path, timeout_seconds)
    run.advance(RunStage.PATCH_VERIFIED)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"public patched tests: {'PASS' if patched.passed else 'FAIL'}",
        content=_execution_text("PATCHED PUBLIC TESTS", patched),
    ))

    delta = analyze_test_delta(original, patched)
    immediate_verdict, immediate_reason = _triage_delta(delta)
    if delta.classification == "suite_repaired":
        immediate_verdict = None
        immediate_reason = None

    executions: list[ChallengeExecutionV4] = []
    generation_failures: list[str] = []
    critic_failures: list[str] = []
    critic_rejections: list[str] = []
    seen: set[str] = set()
    challenger_called = False
    critic_called = False
    feedback: str | None = None

    if immediate_verdict is not None:
        verdict = immediate_verdict
        reason = immediate_reason or "Deterministic test-first triage resolved the case."
        run.advance(RunStage.REGRESSION_CHECKED)
    elif delta.classification == "suite_repaired" and delta.fixed_tests:
        challenger_called = True
        for attempt in range(1, max_challenge_attempts + 1):
            try:
                intent = generate_challenge_intent_v4(case, llm, attempt=attempt, feedback=feedback)
            except ChallengeIntentErrorV4 as exc:
                generation_failures.append(str(exc))
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.MODEL_RESPONSE,
                    summary=f"Iteration 4 intent attempt {attempt} rejected structurally: {exc}",
                    content=exc.raw_response,
                    suffix=".txt",
                    metadata={"attempt": attempt, "usable": False},
                ))
                feedback = f"Your previous structured intent was rejected: {exc}. Return a simpler valid intent."
                continue
            except LLMError as exc:
                generation_failures.append(f"provider failure: {exc}")
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.OBSERVATION,
                    summary=f"Iteration 4 intent attempt {attempt} provider failure: {exc}",
                    metadata={"attempt": attempt, "provider_error": True},
                ))
                feedback = "The previous attempt failed to produce a usable response. Return only the required JSON intent."
                continue

            fingerprint = _intent_fingerprint(intent)
            if fingerprint in seen:
                generation_failures.append("duplicate challenge intent")
                feedback = "That intent duplicates a previous challenge. Select a different contract-supported nearby case."
                continue
            seen.add(fingerprint)

            critic_called = True
            try:
                critique = critique_intent_v4(llm, intent)
            except (LLMError, ValueError) as exc:
                critic_failures.append(str(exc))
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.OBSERVATION,
                    summary=f"Iteration 4 critic attempt {attempt} failed: {exc}",
                    metadata={"attempt": attempt, "critic_failure": True},
                ))
                feedback = "The contract critic could not validate that intent. Choose a simpler directly stated requirement."
                continue

            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.MODEL_RESPONSE,
                summary=f"Iteration 4 intent critic: {'supported' if critique.supported else 'rejected'}",
                content=critique.raw_response,
                suffix=".json",
                metadata={
                    "attempt": attempt,
                    "supported": critique.supported,
                    "contract_id": intent.contract_id,
                    "target": intent.target,
                },
            ))
            if not critique.supported:
                critic_rejections.append(critique.reason)
                feedback = (
                    "The critic rejected that intent as not directly entailed by the selected contract: "
                    + critique.reason
                    + ". Choose a different directly stated nearby behavior."
                )
                continue

            test_code = compile_intent_to_pytest_v4(intent)
            original_challenge = _run_generated_test(test_code, case.original_path, timeout_seconds)
            patched_challenge = _run_generated_test(test_code, case.patched_path, timeout_seconds)
            classification = _classify(intent, original_challenge, patched_challenge)
            item = ChallengeExecutionV4(intent, test_code, original_challenge, patched_challenge, classification)
            executions.append(item)
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.GENERATED_TEST,
                summary=f"deterministically compiled challenge intent {attempt}",
                content=test_code,
                suffix=".py",
                metadata={
                    "attempt": attempt,
                    "kind": intent.kind,
                    "contract_id": intent.contract_id,
                    "target": intent.target,
                    "expectation_type": intent.expectation_type,
                },
            ))
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"Iteration 4 challenge {attempt}: {classification}",
                content=(
                    _execution_text(f"CHALLENGE {attempt} / ORIGINAL", original_challenge)
                    + "\n"
                    + _execution_text(f"CHALLENGE {attempt} / PATCHED", patched_challenge)
                ),
                metadata={"attempt": attempt, "classification": classification},
            ))
            if item.is_counterexample:
                break
            if classification == "survived":
                feedback = "That supported nearby intent survived the patch. Choose a different contract-supported nearby risk."
            else:
                feedback = "That supported intent did not yield decisive execution evidence. Choose a different simpler nearby risk."

        run.advance(RunStage.CHALLENGED)
        regressions = [x for x in executions if x.classification == "regression_counterexample"]
        remaining = [x for x in executions if x.classification == "remaining_requirement_counterexample"]
        survivors = [x for x in executions if x.classification == "survived"]
        if regressions:
            verdict = Verdict.REGRESSION_INTRODUCED
            reason = "Intent-first Challenger found a critic-approved contract test that passes on the original but fails on the patch."
        elif remaining:
            verdict = Verdict.PARTIAL_FIX
            reason = "Intent-first Challenger found a critic-approved remaining requirement that still fails on both original and patch."
        elif len(survivors) >= 2:
            verdict = Verdict.COMPLETE_FIX
            reason = "The public trigger is repaired and two distinct critic-approved nearby intents survived the patch within the bounded challenge budget."
        else:
            verdict = Verdict.INCONCLUSIVE
            reason = "The public trigger is repaired, but Iteration 4 did not collect a critic-approved counterexample or enough independent survived intents for completeness."
        run.advance(RunStage.REGRESSION_CHECKED)
    else:
        verdict = Verdict.INCONCLUSIVE
        reason = "Public evidence did not establish a repaired trigger, so Iteration 4 did not spend challenge budget."
        run.advance(RunStage.REGRESSION_CHECKED)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 4 separates semantic intent generation, semantic contract criticism, deterministic test compilation, and deterministic execution",
        metadata={
            "challenger_called": challenger_called,
            "critic_called": critic_called,
            "challenge_candidates": len(executions),
            "challenge_counterexamples": sum(x.is_counterexample for x in executions),
            "challenge_generation_failures": len(generation_failures),
            "critic_failures": len(critic_failures),
            "critic_rejections": len(critic_rejections),
            "oracle_used": False,
            "hidden_tests_used": False,
        },
    ))
    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 4 verdict: {verdict.value}",
        content=json.dumps({"verdict": verdict.value, "reason": reason}),
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_4",
        "iteration": "4",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": delta.classification,
        "challenger_called": challenger_called,
        "critic_called": critic_called,
        "challenge_generation_failures": len(generation_failures),
        "critic_failures": len(critic_failures),
        "critic_rejections": len(critic_rejections),
        "challenge_candidates": len(executions),
        "challenge_counterexamples": sum(x.is_counterexample for x in executions),
        "challenge_classifications": [x.classification for x in executions],
        "capabilities": {
            "test_first_routing": True,
            "intent_first_challenger": True,
            "contract_id_grounding": True,
            "structured_intent_critic": True,
            "deterministic_test_compilation": True,
            "deterministic_challenge_execution": True,
            "bounded_challenge_retry": True,
            "oracle_visible_to_agents": False,
            "hidden_tests_visible_to_agents": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV4(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        original=original,
        patched=patched,
        test_delta=delta,
        challenge_executions=tuple(executions),
        challenge_generation_failures=tuple(generation_failures),
        critic_failures=tuple(critic_failures),
        critic_rejections=tuple(critic_rejections),
        investigator_called=False,
        challenger_called=challenger_called,
        critic_called=critic_called,
        verifier_called=False,
        run_root=store.root,
    )
