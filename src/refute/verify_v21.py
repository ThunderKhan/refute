from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.investigator import Investigation
from .agents.reproducer import (
    ReproductionCandidate,
    ReproductionGenerationError,
    generate_reproduction,
)
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun
from .verify_v2 import (
    VERIFIER_SYSTEM_PROMPT,
    _enforce_evidence_gate,
    _execution_text,
    _generation_feedback,
    _investigate_with_retry,
    _parse_verdict,
    _run_generated_test,
    _verifier_complete_with_retry,
)


@dataclass(frozen=True, slots=True)
class ReproductionAttemptResultV21:
    candidate: ReproductionCandidate
    original: ExecutionResult
    patched: ExecutionResult | None
    original_failed: bool
    patch_passed: bool
    discriminating: bool


@dataclass(frozen=True, slots=True)
class VerificationResultV21:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation
    original: ExecutionResult
    patched: ExecutionResult
    reproduction_attempts: tuple[ReproductionAttemptResultV21, ...]
    discriminating_reproduction: ReproductionAttemptResultV21 | None
    generation_failures: tuple[str, ...]
    run_root: Path


def _non_discriminating_feedback(
    original: ExecutionResult,
    patched: ExecutionResult | None,
) -> str:
    if original.timed_out:
        return (
            "The prior generated test timed out on the original, so it cannot establish the reported bug. "
            "Generate a smaller, deterministic test.\n\n"
            + _execution_text("PRIOR ORIGINAL REPRODUCTION RUN", original)
        )
    if original.passed:
        return (
            "The prior generated test passed on the original, so it did not reproduce the reported bug. "
            "Revise it to target the exact reported failure.\n\n"
            + _execution_text("PRIOR ORIGINAL REPRODUCTION RUN", original)
        )

    assert patched is not None
    return (
        "The prior generated test failed on BOTH the original and the patch. This is non-discriminating evidence, "
        "not a successful reproduction. The test may assert the wrong behavior or fail for an unrelated reason. "
        "Revise it so it fails for the reported bug on the original and passes when that bug is fixed.\n\n"
        + _execution_text("PRIOR ORIGINAL REPRODUCTION RUN", original)
        + "\n"
        + _execution_text("PRIOR PATCHED REPRODUCTION RUN", patched)
    )


def _complete_fix_forbidden_reasons_v21(patched: ExecutionResult) -> tuple[str, ...]:
    if patched.timed_out:
        return ("the patched existing test suite timed out",)
    if not patched.passed:
        return ("the patched existing test suite failed",)
    return ()


def verify_case_v21(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_reproduction_attempts: int = 3,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV21:
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
        metadata={"iteration": "2.1"},
    ))

    investigation = _investigate_with_retry(
        case, llm, store, run, max_attempts=max_provider_attempts
    )
    run.advance(RunStage.INVESTIGATED)
    run.attach(store.record(
        stage=RunStage.INVESTIGATED.value,
        kind=EvidenceKind.MODEL_RESPONSE,
        summary="Investigator produced structured verification hypothesis",
        content=json.dumps(investigation.to_dict(), indent=2) + "\n",
        suffix=".json",
    ))

    attempts: list[ReproductionAttemptResultV21] = []
    generation_failures: list[str] = []
    discriminating: ReproductionAttemptResultV21 | None = None
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
            message = str(exc)
            generation_failures.append(message)
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.MODEL_RESPONSE,
                summary=f"Reproducer attempt {attempt_no} was unusable: {message}",
                content=exc.raw_response,
                suffix=".txt",
                metadata={"attempt": attempt_no, "usable": False, "error": message},
            ))
            feedback = _generation_feedback(message)
            continue
        except LLMError as exc:
            message = f"provider failure: {exc}"
            generation_failures.append(message)
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Reproducer attempt {attempt_no} provider failure: {exc}",
                metadata={
                    "attempt": attempt_no,
                    "usable": False,
                    "provider_error": True,
                    "error": str(exc),
                },
            ))
            feedback = _generation_feedback(message)
            continue

        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.GENERATED_TEST,
            summary=f"Reproducer generated attempt {attempt_no}: {candidate.rationale}",
            content=candidate.test_code,
            suffix=".py",
            metadata={"attempt": attempt_no, "rationale": candidate.rationale},
        ))

        original_repro = _run_generated_test(
            candidate.test_code, case.original_path, timeout_seconds
        )
        original_failed = not original_repro.passed and not original_repro.timed_out
        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.TEST_RESULT,
            summary=(
                f"reproduction attempt {attempt_no} on original: "
                f"{'FAIL' if original_failed else 'PASS_OR_TIMEOUT'}"
            ),
            content=_execution_text(
                f"REPRODUCTION ATTEMPT {attempt_no} / ORIGINAL", original_repro
            ),
            metadata={
                "attempt": attempt_no,
                "passed": original_repro.passed,
                "timed_out": original_repro.timed_out,
                "original_failed": original_failed,
            },
        ))

        patched_repro: ExecutionResult | None = None
        patch_passed = False
        is_discriminating = False
        if original_failed:
            patched_repro = _run_generated_test(
                candidate.test_code, case.patched_path, timeout_seconds
            )
            patch_passed = patched_repro.passed and not patched_repro.timed_out
            is_discriminating = patch_passed
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=(
                    f"reproduction attempt {attempt_no} on patch: "
                    f"{'PASS' if patch_passed else 'FAIL_OR_TIMEOUT'}"
                ),
                content=_execution_text(
                    f"REPRODUCTION ATTEMPT {attempt_no} / PATCHED", patched_repro
                ),
                metadata={
                    "attempt": attempt_no,
                    "passed": patched_repro.passed,
                    "timed_out": patched_repro.timed_out,
                    "patch_passed": patch_passed,
                    "discriminating": is_discriminating,
                },
            ))

        attempt_result = ReproductionAttemptResultV21(
            candidate=candidate,
            original=original_repro,
            patched=patched_repro,
            original_failed=original_failed,
            patch_passed=patch_passed,
            discriminating=is_discriminating,
        )
        attempts.append(attempt_result)

        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.OBSERVATION,
            summary=(
                f"reproduction attempt {attempt_no}: "
                f"{'DISCRIMINATING' if is_discriminating else 'NON_DISCRIMINATING'}"
            ),
            metadata={
                "attempt": attempt_no,
                "original_failed": original_failed,
                "patch_passed": patch_passed,
                "discriminating": is_discriminating,
            },
        ))

        if is_discriminating:
            discriminating = attempt_result
            break

        feedback = _non_discriminating_feedback(original_repro, patched_repro)

    run.advance(RunStage.REPRODUCTION_ATTEMPTED)

    original = run_command(case.test_command, case.original_path, timeout_seconds)
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.attach(store.record(
        stage=RunStage.ORIGINAL_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on original: {'PASS' if original.passed else 'FAIL'}",
        content=_execution_text("ORIGINAL EXISTING TESTS", original),
        metadata={
            "passed": original.passed,
            "exit_code": original.exit_code,
            "timed_out": original.timed_out,
        },
    ))

    patched = run_command(case.test_command, case.patched_path, timeout_seconds)
    run.advance(RunStage.PATCH_VERIFIED)
    run.attach(store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on patch: {'PASS' if patched.passed else 'FAIL'}",
        content=_execution_text("PATCHED EXISTING TESTS", patched),
        metadata={
            "passed": patched.passed,
            "exit_code": patched.exit_code,
            "timed_out": patched.timed_out,
        },
    ))

    run.advance(RunStage.REGRESSION_CHECKED)
    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary=(
            "Iteration 2.1 accepts generated reproduction evidence only when the same test "
            "fails on original and passes on patch; no Challenger cases yet"
        ),
        metadata={
            "generated_reproduction": True,
            "discriminating_reproduction_required": True,
            "challenger_used": False,
        },
    ))

    reproduction_payload = [
        {
            "attempt": item.candidate.attempt,
            "rationale": item.candidate.rationale,
            "original": {
                "passed": item.original.passed,
                "exit_code": item.original.exit_code,
                "timed_out": item.original.timed_out,
                "stdout": item.original.stdout,
                "stderr": item.original.stderr,
            },
            "patched": None if item.patched is None else {
                "passed": item.patched.passed,
                "exit_code": item.patched.exit_code,
                "timed_out": item.patched.timed_out,
                "stdout": item.patched.stdout,
                "stderr": item.patched.stderr,
            },
            "original_failed": item.original_failed,
            "patch_passed": item.patch_passed,
            "discriminating": item.discriminating,
        }
        for item in attempts
    ]

    forbidden_reasons = _complete_fix_forbidden_reasons_v21(patched)
    verifier_input = {
        "iteration": "2.1",
        "investigation": investigation.to_dict(),
        "existing_tests": {
            "original": {
                "passed": original.passed,
                "exit_code": original.exit_code,
                "stdout": original.stdout,
                "stderr": original.stderr,
            },
            "patched": {
                "passed": patched.passed,
                "exit_code": patched.exit_code,
                "stdout": patched.stdout,
                "stderr": patched.stderr,
            },
        },
        "reproduction_attempts": reproduction_payload,
        "reproduction_generation_failures": generation_failures,
        "discriminating_reproduction_found": discriminating is not None,
        "reproduction_semantics": (
            "Only original FAIL + patch PASS counts as a successful, discriminating reproduction. "
            "Original FAIL + patch FAIL is non-discriminating and must not be treated as proof of the reported bug."
        ),
        "complete_fix_forbidden_reasons": list(forbidden_reasons),
        "limitations": ["no challenger-generated nearby cases"],
    }

    raw_verdict = _verifier_complete_with_retry(
        llm,
        json.dumps(verifier_input, indent=2),
        store,
        run,
        max_attempts=max_provider_attempts,
    )
    proposed_verdict, proposed_reason = _parse_verdict(raw_verdict)
    verdict, reason, gate_overrode_model = _enforce_evidence_gate(
        proposed_verdict,
        proposed_reason,
        forbidden_reasons,
    )

    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"evidence-constrained verdict: {verdict.value}",
        content=raw_verdict,
        metadata={
            "proposed_verdict": proposed_verdict.value,
            "final_verdict": verdict.value,
            "reason": reason,
            "evidence_gate_overrode_model": gate_overrode_model,
            "complete_fix_forbidden_reasons": list(forbidden_reasons),
            "discriminating_reproduction_found": discriminating is not None,
        },
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_2_1",
        "iteration": "2.1",
        "verdict": verdict.value,
        "reason": reason,
        "model_proposed_verdict": proposed_verdict.value,
        "model_proposed_reason": proposed_reason,
        "evidence_gate_overrode_model": gate_overrode_model,
        "complete_fix_forbidden_reasons": list(forbidden_reasons),
        "stages": run.events,
        "evidence_count": len(run.evidence),
        "reproduction_attempts": len(attempts),
        "reproduction_generation_failures": len(generation_failures),
        "discriminating_reproduction_found": discriminating is not None,
        "capabilities": {
            "investigator": True,
            "existing_test_execution": True,
            "generated_reproduction": True,
            "bounded_reproduction_retry": True,
            "generation_failure_recovery": True,
            "provider_timeout_recovery": True,
            "deterministic_verdict_gate": True,
            "discriminating_reproduction_semantics": True,
            "challenger": False,
        },
    }
    (store.root / "result.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return VerificationResultV21(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        investigation=investigation,
        original=original,
        patched=patched,
        reproduction_attempts=tuple(attempts),
        discriminating_reproduction=discriminating,
        generation_failures=tuple(generation_failures),
        run_root=store.root,
    )
