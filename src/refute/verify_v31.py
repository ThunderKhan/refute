from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.challenger_v31 import (
    ChallengeCandidateV31,
    ChallengeGenerationErrorV31,
    generate_challenge_v31,
)
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
class ChallengeExecutionV31:
    candidate: ChallengeCandidateV31
    original: ExecutionResult
    patched: ExecutionResult
    classification: str

    @property
    def is_counterexample(self) -> bool:
        return self.classification in {"regression_counterexample", "remaining_requirement_counterexample"}


@dataclass(frozen=True, slots=True)
class VerificationResultV31:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    investigation: Investigation | None
    challenge_executions: tuple[ChallengeExecutionV31, ...]
    challenge_generation_failures: tuple[str, ...]
    investigator_called: bool
    challenger_called: bool
    verifier_called: bool
    run_root: Path


def _classify(candidate: ChallengeCandidateV31, original: ExecutionResult, patched: ExecutionResult) -> str:
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
        return "That grounded nearby test passed on the patch. Try a different issue-grounded risk, not the same behavior."
    if classification == "non_decisive":
        return "The test failed on both versions but was not declared as a remaining_requirement. Choose the correct kind and cite the exact issue requirement."
    if classification == "invalid_execution":
        return "The generated test did not produce a valid pytest pass/fail result. Generate a simpler focused pytest assertion."
    return "Try a different grounded nearby risk."


def verify_case_v31(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_challenge_attempts: int = 2,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV31:
    if max_challenge_attempts < 1:
        raise ValueError("max_challenge_attempts must be at least 1")
    if max_provider_attempts < 1:
        raise ValueError("max_provider_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="case loaded; oracle and hidden tests withheld from Iteration 3.1 agents",
        metadata={"iteration": "3.1"},
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

    investigation: Investigation | None = None
    executions: list[ChallengeExecutionV31] = []
    generation_failures: list[str] = []
    investigator_called = False
    challenger_called = False
    verifier_called = False

    if immediate_verdict is not None:
        verdict = immediate_verdict
        reason = immediate_reason or "Deterministic test-first triage resolved the case."
        run.advance(RunStage.REGRESSION_CHECKED)
    elif delta.classification == "suite_repaired" and delta.fixed_tests:
        investigator_called = True
        investigation = _investigate_with_retry(case, llm, store, run, max_attempts=max_provider_attempts)
        run.advance(RunStage.INVESTIGATED)
        run.attach(store.record(
            stage=RunStage.INVESTIGATED.value,
            kind=EvidenceKind.MODEL_RESPONSE,
            summary="Investigator framed grounded nearby risks for Challenger 3.1",
            content=json.dumps(investigation.to_dict(), indent=2) + "\n",
            suffix=".json",
        ))

        challenger_called = True
        feedback: str | None = None
        for attempt in range(1, max_challenge_attempts + 1):
            try:
                candidate = generate_challenge_v31(
                    case, investigation, llm, attempt=attempt, feedback=feedback
                )
            except ChallengeGenerationErrorV31 as exc:
                generation_failures.append(str(exc))
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.MODEL_RESPONSE,
                    summary=f"Challenger attempt {attempt} rejected by grounding/safety gate: {exc}",
                    content=exc.raw_response,
                    suffix=".txt",
                    metadata={"attempt": attempt, "usable": False},
                ))
                feedback = str(exc)
                continue
            except LLMError as exc:
                generation_failures.append(f"provider failure: {exc}")
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.OBSERVATION,
                    summary=f"Challenger attempt {attempt} provider failure: {exc}",
                    metadata={"attempt": attempt, "provider_error": True},
                ))
                feedback = str(exc)
                continue

            original_challenge = _run_generated_test(candidate.test_code, case.original_path, timeout_seconds)
            patched_challenge = _run_generated_test(candidate.test_code, case.patched_path, timeout_seconds)
            classification = _classify(candidate, original_challenge, patched_challenge)
            item = ChallengeExecutionV31(candidate, original_challenge, patched_challenge, classification)
            executions.append(item)
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"grounded challenge attempt {attempt}: {classification}",
                content=(
                    _execution_text(f"CHALLENGE {attempt} / ORIGINAL", original_challenge)
                    + "\n"
                    + _execution_text(f"CHALLENGE {attempt} / PATCHED", patched_challenge)
                ),
                metadata={
                    "attempt": attempt,
                    "kind": candidate.kind,
                    "grounding_quote": candidate.grounding_quote,
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
            reason = "Grounded Challenger found a nearby issue-supported test that passes on the original but fails on the patch."
        elif remaining:
            verdict = Verdict.PARTIAL_FIX
            reason = "Grounded Challenger found an explicitly issue-supported remaining requirement that fails on both original and patch after the public trigger was repaired."
        elif executions and all(x.classification == "survived" for x in executions):
            verdict = Verdict.COMPLETE_FIX
            reason = "The public trigger is repaired and all valid issue-grounded Challenger tests survived the patch within the bounded challenge budget."
        else:
            verdict = Verdict.INCONCLUSIVE
            reason = "The public trigger is repaired, but Challenger 3.1 produced insufficient valid grounded evidence for a complete or negative verdict."
        run.advance(RunStage.REGRESSION_CHECKED)
    else:
        verdict = Verdict.INCONCLUSIVE
        reason = "Public evidence did not establish a repaired trigger, so Iteration 3.1 did not spend challenge budget."
        run.advance(RunStage.REGRESSION_CHECKED)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 3.1 uses exact issue-quote grounding and bounded one-candidate challenge retries",
        metadata={
            "investigator_called": investigator_called,
            "challenger_called": challenger_called,
            "challenge_attempts_executed": len(executions),
            "counterexamples": sum(x.is_counterexample for x in executions),
            "oracle_used": False,
            "hidden_tests_used": False,
        },
    ))
    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 3.1 verdict: {verdict.value}",
        content=json.dumps({"verdict": verdict.value, "reason": reason}),
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_3_1",
        "iteration": "3.1",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": delta.classification,
        "investigator_called": investigator_called,
        "challenger_called": challenger_called,
        "challenge_generation_failures": len(generation_failures),
        "challenge_attempts_executed": len(executions),
        "challenge_counterexamples": sum(x.is_counterexample for x in executions),
        "challenge_classifications": [x.classification for x in executions],
        "capabilities": {
            "test_first_routing": True,
            "grounded_challenger": True,
            "exact_issue_quote_gate": True,
            "single_candidate_generation": True,
            "bounded_challenge_retry": True,
            "oracle_visible_to_agents": False,
            "hidden_tests_visible_to_agents": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV31(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        original=original,
        patched=patched,
        test_delta=delta,
        investigation=investigation,
        challenge_executions=tuple(executions),
        challenge_generation_failures=tuple(generation_failures),
        investigator_called=investigator_called,
        challenger_called=challenger_called,
        verifier_called=verifier_called,
        run_root=store.root,
    )
