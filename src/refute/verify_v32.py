from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.challenger_v32 import (
    ChallengeCandidateV32,
    ChallengeGenerationErrorV32,
    generate_challenge_v32,
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
class ChallengeExecutionV32:
    candidate: ChallengeCandidateV32
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
class VerificationResultV32:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    challenge_executions: tuple[ChallengeExecutionV32, ...]
    challenge_generation_failures: tuple[str, ...]
    investigator_called: bool
    challenger_called: bool
    verifier_called: bool
    run_root: Path


def _classify(candidate: ChallengeCandidateV32, original: ExecutionResult, patched: ExecutionResult) -> str:
    if original.timed_out or patched.timed_out:
        return "invalid_execution"
    if original.exit_code not in {0, 1} or patched.exit_code not in {0, 1}:
        return "invalid_execution"
    if patched.passed:
        return "survived"
    if original.passed:
        return "regression_counterexample"
    if candidate.kind == "remaining_requirement" and original.exit_code == 1 and patched.exit_code == 1:
        return "remaining_requirement_counterexample"
    return "non_decisive"


def _feedback(classification: str) -> str:
    if classification == "survived":
        return "That contract-grounded test passed on the patch. Choose a different supplied contract span or a different nearby risk."
    if classification == "non_decisive":
        return "The test failed on both versions but was not a qualified remaining_requirement. Re-check kind and selected contract_id."
    if classification == "invalid_execution":
        return "The generated test did not produce a valid pytest pass/fail result. Generate simpler Python using the repository's actual public API."
    return "Choose a different supplied contract span or nearby risk."


def verify_case_v32(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_challenge_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV32:
    if max_challenge_attempts < 1:
        raise ValueError("max_challenge_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="case loaded; oracle and hidden tests withheld from Iteration 3.2",
        metadata={"iteration": "3.2", "routing": "test_first_then_contract_grounded_challenge"},
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

    executions: list[ChallengeExecutionV32] = []
    generation_failures: list[str] = []
    challenger_called = False
    investigator_called = False
    verifier_called = False

    if immediate_verdict is not None:
        verdict = immediate_verdict
        reason = immediate_reason or "Deterministic test-first triage resolved the case."
        run.advance(RunStage.REGRESSION_CHECKED)
    elif delta.classification == "suite_repaired" and delta.fixed_tests:
        challenger_called = True
        feedback: str | None = None
        for attempt in range(1, max_challenge_attempts + 1):
            try:
                candidate = generate_challenge_v32(
                    case,
                    llm,
                    attempt=attempt,
                    feedback=feedback,
                )
            except ChallengeGenerationErrorV32 as exc:
                generation_failures.append(str(exc))
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.MODEL_RESPONSE,
                    summary=f"Challenger 3.2 attempt {attempt} rejected: {exc}",
                    content=exc.raw_response,
                    suffix=".txt",
                    metadata={"attempt": attempt, "usable": False, "error": str(exc)},
                ))
                feedback = str(exc)
                continue
            except LLMError as exc:
                generation_failures.append(f"provider failure: {exc}")
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.OBSERVATION,
                    summary=f"Challenger 3.2 attempt {attempt} provider failure: {exc}",
                    metadata={"attempt": attempt, "provider_error": True},
                ))
                feedback = str(exc)
                continue

            original_challenge = _run_generated_test(candidate.test_code, case.original_path, timeout_seconds)
            patched_challenge = _run_generated_test(candidate.test_code, case.patched_path, timeout_seconds)
            classification = _classify(candidate, original_challenge, patched_challenge)
            item = ChallengeExecutionV32(candidate, original_challenge, patched_challenge, classification)
            executions.append(item)
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"contract-grounded challenge {attempt}: {classification}",
                content=(
                    _execution_text(f"CHALLENGE {attempt} / ORIGINAL", original_challenge)
                    + "\n"
                    + _execution_text(f"CHALLENGE {attempt} / PATCHED", patched_challenge)
                ),
                metadata={
                    "attempt": attempt,
                    "kind": candidate.kind,
                    "contract_id": candidate.contract_id,
                    "contract_text": candidate.contract_text,
                    "classification": classification,
                },
            ))
            if item.is_counterexample:
                break
            feedback = _feedback(classification)

        run.advance(RunStage.CHALLENGED)
        regressions = [x for x in executions if x.classification == "regression_counterexample"]
        remaining = [x for x in executions if x.classification == "remaining_requirement_counterexample"]
        if regressions:
            verdict = Verdict.REGRESSION_INTRODUCED
            reason = "Contract-grounded Challenger found a nearby test that passes on the original but fails on the patch."
        elif remaining:
            verdict = Verdict.PARTIAL_FIX
            reason = "Contract-grounded Challenger found a selected public-issue requirement that still fails on both original and patch after the reported trigger was repaired."
        elif executions and all(x.classification == "survived" for x in executions):
            verdict = Verdict.COMPLETE_FIX
            reason = "The public trigger is repaired and all valid contract-grounded Challenger tests survived the patch within the bounded challenge budget."
        else:
            verdict = Verdict.INCONCLUSIVE
            reason = "The public trigger is repaired, but Iteration 3.2 produced insufficient valid executable challenge evidence."
        run.advance(RunStage.REGRESSION_CHECKED)
    else:
        verdict = Verdict.INCONCLUSIVE
        reason = "Public evidence did not establish a repaired trigger, so Iteration 3.2 did not spend challenge budget."
        run.advance(RunStage.REGRESSION_CHECKED)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 3.2 replaces fragile free-form quote copying with deterministic contract IDs",
        metadata={
            "investigator_called": investigator_called,
            "challenger_called": challenger_called,
            "challenge_candidates": len(executions),
            "challenge_counterexamples": sum(x.is_counterexample for x in executions),
            "challenge_generation_failures": len(generation_failures),
            "oracle_used": False,
            "hidden_tests_used": False,
        },
    ))
    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 3.2 verdict: {verdict.value}",
        content=json.dumps({"verdict": verdict.value, "reason": reason}),
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_3_2",
        "iteration": "3.2",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": delta.classification,
        "investigator_called": False,
        "challenger_called": challenger_called,
        "challenge_generation_failures": len(generation_failures),
        "challenge_candidates": len(executions),
        "challenge_counterexamples": sum(x.is_counterexample for x in executions),
        "challenge_classifications": [x.classification for x in executions],
        "capabilities": {
            "test_first_routing": True,
            "deterministic_contract_extraction": True,
            "contract_id_grounding": True,
            "single_candidate_generation": True,
            "bounded_challenge_retry": True,
            "investigator_required_for_challenge": False,
            "oracle_visible_to_agents": False,
            "hidden_tests_visible_to_agents": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV32(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        original=original,
        patched=patched,
        test_delta=delta,
        challenge_executions=tuple(executions),
        challenge_generation_failures=tuple(generation_failures),
        investigator_called=False,
        challenger_called=challenger_called,
        verifier_called=False,
        run_root=store.root,
    )
