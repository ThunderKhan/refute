from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.investigator import Investigation
from .agents.reproducer import ReproductionGenerationError, generate_reproduction
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun
from .verify_v2 import (
    _execution_text,
    _generation_feedback,
    _investigate_with_retry,
    _parse_verdict,
    _run_generated_test,
)
from .verify_v21 import _non_discriminating_feedback
from .verify_v22 import ReproductionAttemptResultV22, _classify_attempt
from .verify_v23 import TestDelta, analyze_test_delta


VERIFIER_SYSTEM_PROMPT_V24 = """You are the semantic fallback verifier in a software patch verification system.
You are called only after deterministic test-first triage could not decide the observed outcome.

Rules:
- Never contradict deterministic execution evidence.
- A generated reproduction is high-confidence only when it fails on the original and passes on the patch.
- Non-discriminating or not-reproduced generated tests cannot establish patch failure.
- Prefer inconclusive when the available evidence cannot distinguish the verdict.

Return exactly one JSON object:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief explanation grounded in supplied evidence"
}
"""


@dataclass(frozen=True, slots=True)
class VerificationResultV24:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation | None
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    reproduction_attempts: tuple[ReproductionAttemptResultV22, ...]
    discriminating_reproduction: ReproductionAttemptResultV22 | None
    generation_failures: tuple[str, ...]
    investigator_called: bool
    verifier_called: bool
    run_root: Path


def _triage_delta(delta: TestDelta) -> tuple[Verdict | None, str | None]:
    if delta.deterministic_verdict is not None:
        return (
            delta.deterministic_verdict,
            f"Deterministic test-first triage: {delta.reason}.",
        )

    # On the current controlled benchmark, an observed failing test that becomes
    # clean on the patch is itself a discriminating executable witness. We call
    # this complete only with respect to the observed suite, not a proof of global
    # correctness. Challenger/hidden-oracle coverage is still needed later.
    if delta.classification == "suite_repaired" and delta.fixed_tests:
        return (
            Verdict.COMPLETE_FIX,
            "Deterministic test-first triage: every observed failing test now passes, "
            "and no new or remaining suite failures were observed.",
        )

    # If the original suite already passes, the reported bug was not reproduced by
    # the available deterministic evidence. Calling the patch fixed would fabricate
    # causality, so remain inconclusive without spending model calls.
    if delta.classification == "both_pass":
        return (
            Verdict.INCONCLUSIVE,
            "Deterministic test-first triage: both original and patched suites pass, "
            "so the reported failure was not reproduced and patch effectiveness cannot be established.",
        )

    return None, None


def _verifier_complete(
    llm: LLM,
    payload: str,
    store: EvidenceStore,
    run: VerificationRun,
    *,
    max_attempts: int,
) -> str:
    last_error: LLMError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm.complete(VERIFIER_SYSTEM_PROMPT_V24, payload)
        except LLMError as exc:
            last_error = exc
            run.attach(store.record(
                stage=RunStage.REGRESSION_CHECKED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Fallback verifier provider attempt {attempt} failed: {exc}",
                metadata={"attempt": attempt, "component": "verifier", "provider_error": True},
            ))
    assert last_error is not None
    raise LLMError(
        f"fallback verifier failed after {max_attempts} provider attempts: {last_error}"
    ) from last_error


def verify_case_v24(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_reproduction_attempts: int = 2,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV24:
    if max_reproduction_attempts < 1:
        raise ValueError("max_reproduction_attempts must be at least 1")
    if max_provider_attempts < 1:
        raise ValueError("max_provider_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="verification case loaded; benchmark oracle withheld from agents",
        metadata={"iteration": "2.4", "routing": "test_first"},
    ))

    # Cheap deterministic evidence comes first. A provider outage must not block a
    # case that can already be resolved mechanically.
    original = run_command(case.test_command, case.original_path, timeout_seconds)
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.attach(store.record(
        stage=RunStage.ORIGINAL_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on original: {'PASS' if original.passed else 'FAIL'}",
        content=_execution_text("ORIGINAL EXISTING TESTS", original),
        metadata={"passed": original.passed, "exit_code": original.exit_code, "timed_out": original.timed_out},
    ))

    patched = run_command(case.test_command, case.patched_path, timeout_seconds)
    run.advance(RunStage.PATCH_VERIFIED)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on patch: {'PASS' if patched.passed else 'FAIL'}",
        content=_execution_text("PATCHED EXISTING TESTS", patched),
        metadata={"passed": patched.passed, "exit_code": patched.exit_code, "timed_out": patched.timed_out},
    ))

    delta = analyze_test_delta(original, patched)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.OBSERVATION,
        summary=f"deterministic test delta: {delta.classification}",
        content=json.dumps({
            "original_failures": delta.original_failures,
            "patched_failures": delta.patched_failures,
            "fixed_tests": delta.fixed_tests,
            "remaining_failures": delta.remaining_failures,
            "new_failures": delta.new_failures,
            "classification": delta.classification,
            "deterministic_verdict": None if delta.deterministic_verdict is None else delta.deterministic_verdict.value,
            "reason": delta.reason,
        }, indent=2) + "\n",
        suffix=".json",
    ))

    verdict, reason = _triage_delta(delta)
    investigation: Investigation | None = None
    attempts: list[ReproductionAttemptResultV22] = []
    generation_failures: list[str] = []
    discriminating: ReproductionAttemptResultV22 | None = None
    investigator_called = False
    verifier_called = False
    raw_verdict: str

    if verdict is not None:
        run.advance(RunStage.REGRESSION_CHECKED)
        raw_verdict = json.dumps({"verdict": verdict.value, "reason": reason})
    else:
        # Only genuinely ambiguous deterministic outcomes pay for semantic agents.
        investigator_called = True
        investigation = _investigate_with_retry(
            case, llm, store, run, max_attempts=max_provider_attempts
        )
        run.advance(RunStage.INVESTIGATED)
        run.attach(store.record(
            stage=RunStage.INVESTIGATED.value,
            kind=EvidenceKind.MODEL_RESPONSE,
            summary="Investigator invoked after ambiguous deterministic triage",
            content=json.dumps(investigation.to_dict(), indent=2) + "\n",
            suffix=".json",
        ))

        feedback: str | None = None
        for attempt_no in range(1, max_reproduction_attempts + 1):
            try:
                candidate = generate_reproduction(
                    case,
                    investigation,
                    llm,
                    attempt=attempt_no,
                    feedback=feedback,
                )
            except ReproductionGenerationError as exc:
                generation_failures.append(str(exc))
                run.attach(store.record(
                    stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                    kind=EvidenceKind.MODEL_RESPONSE,
                    summary=f"Reproducer attempt {attempt_no} was unusable: {exc}",
                    content=exc.raw_response,
                    suffix=".txt",
                    metadata={"attempt": attempt_no, "usable": False, "error": str(exc)},
                ))
                feedback = _generation_feedback(str(exc))
                continue
            except LLMError as exc:
                generation_failures.append(f"provider failure: {exc}")
                run.attach(store.record(
                    stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                    kind=EvidenceKind.OBSERVATION,
                    summary=f"Reproducer attempt {attempt_no} provider failure: {exc}",
                    metadata={"attempt": attempt_no, "provider_error": True},
                ))
                feedback = _generation_feedback(str(exc))
                continue

            original_repro = _run_generated_test(
                candidate.test_code, case.original_path, timeout_seconds
            )
            patched_repro: ExecutionResult | None = None
            if not original_repro.passed and not original_repro.timed_out:
                patched_repro = _run_generated_test(
                    candidate.test_code, case.patched_path, timeout_seconds
                )
            classification, weight = _classify_attempt(original_repro, patched_repro)
            item = ReproductionAttemptResultV22(
                candidate, original_repro, patched_repro, classification, weight
            )
            attempts.append(item)
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"reproduction attempt {attempt_no}: {classification.upper()} ({weight} weight)",
                content=(
                    _execution_text(
                        f"REPRODUCTION ATTEMPT {attempt_no} / ORIGINAL", original_repro
                    )
                    + (
                        "\n"
                        + _execution_text(
                            f"REPRODUCTION ATTEMPT {attempt_no} / PATCHED", patched_repro
                        )
                        if patched_repro
                        else ""
                    )
                ),
                metadata={
                    "attempt": attempt_no,
                    "classification": classification,
                    "evidence_weight": weight,
                },
            ))
            if classification == "discriminating":
                discriminating = item
                break
            feedback = _non_discriminating_feedback(original_repro, patched_repro)

        run.advance(RunStage.REPRODUCTION_ATTEMPTED)
        run.advance(RunStage.REGRESSION_CHECKED)
        verifier_called = True
        payload = {
            "iteration": "2.4",
            "investigation": investigation.to_dict(),
            "test_delta": {
                "classification": delta.classification,
                "reason": delta.reason,
                "fixed_tests": delta.fixed_tests,
                "remaining_failures": delta.remaining_failures,
                "new_failures": delta.new_failures,
            },
            "reproduction_attempts": [
                {
                    "classification": item.classification,
                    "evidence_weight": item.evidence_weight,
                }
                for item in attempts
            ],
            "discriminating_reproduction_found": discriminating is not None,
            "limitations": ["no Challenger-generated nearby cases"],
        }
        raw_verdict = _verifier_complete(
            llm,
            json.dumps(payload, indent=2),
            store,
            run,
            max_attempts=max_provider_attempts,
        )
        verdict, reason = _parse_verdict(raw_verdict)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 2.4 routes deterministic test evidence before optional agent calls",
        metadata={
            "test_first_routing": True,
            "investigator_called": investigator_called,
            "verifier_called": verifier_called,
            "challenger_used": False,
        },
    ))
    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 2.4 verdict: {verdict.value}",
        content=raw_verdict,
        metadata={
            "final_verdict": verdict.value,
            "reason": reason,
            "test_delta_classification": delta.classification,
            "investigator_called": investigator_called,
            "verifier_called": verifier_called,
        },
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_2_4",
        "iteration": "2.4",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": {
            "classification": delta.classification,
            "fixed_tests": list(delta.fixed_tests),
            "remaining_failures": list(delta.remaining_failures),
            "new_failures": list(delta.new_failures),
        },
        "reproduction_attempts": len(attempts),
        "reproduction_generation_failures": len(generation_failures),
        "discriminating_reproduction_found": discriminating is not None,
        "investigator_called": investigator_called,
        "verifier_called": verifier_called,
        "capabilities": {
            "test_first_routing": True,
            "existing_test_execution": True,
            "test_delta_engine": True,
            "conditional_investigator": True,
            "conditional_generated_reproduction": True,
            "conditional_verifier": True,
            "challenger": False,
        },
    }
    (store.root / "result.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return VerificationResultV24(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        investigation=investigation,
        original=original,
        patched=patched,
        test_delta=delta,
        reproduction_attempts=tuple(attempts),
        discriminating_reproduction=discriminating,
        generation_failures=tuple(generation_failures),
        investigator_called=investigator_called,
        verifier_called=verifier_called,
        run_root=store.root,
    )
