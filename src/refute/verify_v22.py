from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.investigator import Investigation
from .agents.reproducer import ReproductionCandidate, ReproductionGenerationError, generate_reproduction
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


VERIFIER_SYSTEM_PROMPT_V22 = """You are the evidence-constrained verifier in a software patch verification system.
Use only the supplied Investigator hypothesis and deterministic execution evidence.

Evidence policy for Iteration 2.2:
- Existing test-suite execution is deterministic evidence.
- A generated reproduction is HIGH-CONFIDENCE only when the same test fails on the original and passes on the patch.
- A generated test that fails on both versions is NON-DISCRIMINATING, DIAGNOSTIC-ONLY evidence. It must not be used as proof that the patch is partial, ineffective, or regressing.
- A generated test that passes or times out on the original is NOT-REPRODUCED and carries no negative evidence against the patch.
- Generation/provider failures are operational evidence only.
- Obey `forbidden_verdicts` mechanically. Never return a forbidden verdict.

Do not invent execution facts. If strong evidence is insufficient, prefer inconclusive rather than upgrading diagnostic evidence.
Return exactly one JSON object:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief explanation grounded in the supplied evidence"
}
"""


@dataclass(frozen=True, slots=True)
class ReproductionAttemptResultV22:
    candidate: ReproductionCandidate
    original: ExecutionResult
    patched: ExecutionResult | None
    classification: str
    evidence_weight: str

    @property
    def discriminating(self) -> bool:
        return self.classification == "discriminating"


@dataclass(frozen=True, slots=True)
class VerificationResultV22:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation
    original: ExecutionResult
    patched: ExecutionResult
    reproduction_attempts: tuple[ReproductionAttemptResultV22, ...]
    discriminating_reproduction: ReproductionAttemptResultV22 | None
    generation_failures: tuple[str, ...]
    stopped_for_stagnation: bool
    run_root: Path


def _classify_attempt(
    original: ExecutionResult,
    patched: ExecutionResult | None,
) -> tuple[str, str]:
    if original.timed_out or original.passed:
        return "not_reproduced", "none"
    if patched is not None and patched.passed and not patched.timed_out:
        return "discriminating", "high"
    return "non_discriminating", "diagnostic"


def _attempt_feedback(
    classification: str,
    original: ExecutionResult,
    patched: ExecutionResult | None,
) -> str:
    if classification == "not_reproduced":
        return _non_discriminating_feedback(original, patched)
    assert classification == "non_discriminating"
    return _non_discriminating_feedback(original, patched)


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
            return llm.complete(VERIFIER_SYSTEM_PROMPT_V22, payload)
        except LLMError as exc:
            last_error = exc
            run.attach(store.record(
                stage=RunStage.REGRESSION_CHECKED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Verifier provider attempt {attempt} failed: {exc}",
                metadata={"attempt": attempt, "component": "verifier", "provider_error": True},
            ))
    assert last_error is not None
    raise LLMError(f"verifier failed after {max_attempts} provider attempts: {last_error}") from last_error


def _verdict_constraints(
    patched: ExecutionResult,
    discriminating: ReproductionAttemptResultV22 | None,
) -> dict[Verdict, str]:
    constraints: dict[Verdict, str] = {}
    if patched.timed_out:
        constraints[Verdict.COMPLETE_FIX] = "the patched existing test suite timed out"
    elif not patched.passed:
        constraints[Verdict.COMPLETE_FIX] = "the patched existing test suite failed"

    # Low-confidence generated attempts cannot establish a remaining bug.
    if patched.passed and not patched.timed_out and discriminating is None:
        reason = (
            "the patched existing suite passes and no high-confidence discriminating reproduction exists; "
            "diagnostic/non-reproducing generated tests cannot establish remaining or regressed behavior"
        )
        constraints[Verdict.PARTIAL_FIX] = reason
        constraints[Verdict.INEFFECTIVE_FIX] = reason
        constraints[Verdict.REGRESSION_INTRODUCED] = reason
    return constraints


def _enforce_weighted_gate(
    proposed_verdict: Verdict,
    proposed_reason: str,
    constraints: dict[Verdict, str],
) -> tuple[Verdict, str, bool]:
    reason = constraints.get(proposed_verdict)
    if reason is None:
        return proposed_verdict, proposed_reason, False
    return (
        Verdict.INCONCLUSIVE,
        f"Deterministic evidence-weighting gate rejected the model's {proposed_verdict.value} verdict because {reason}.",
        True,
    )


def verify_case_v22(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_reproduction_attempts: int = 3,
    max_provider_attempts: int = 2,
    stagnation_limit: int = 2,
    run_id: str | None = None,
) -> VerificationResultV22:
    if max_reproduction_attempts < 1:
        raise ValueError("max_reproduction_attempts must be at least 1")
    if max_provider_attempts < 1:
        raise ValueError("max_provider_attempts must be at least 1")
    if stagnation_limit < 1:
        raise ValueError("stagnation_limit must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="verification case loaded; benchmark oracle withheld from agents",
        metadata={"iteration": "2.2"},
    ))

    investigation = _investigate_with_retry(case, llm, store, run, max_attempts=max_provider_attempts)
    run.advance(RunStage.INVESTIGATED)
    run.attach(store.record(
        stage=RunStage.INVESTIGATED.value,
        kind=EvidenceKind.MODEL_RESPONSE,
        summary="Investigator produced structured verification hypothesis",
        content=json.dumps(investigation.to_dict(), indent=2) + "\n",
        suffix=".json",
    ))

    attempts: list[ReproductionAttemptResultV22] = []
    generation_failures: list[str] = []
    discriminating: ReproductionAttemptResultV22 | None = None
    feedback: str | None = None
    consecutive_non_discriminating = 0
    stopped_for_stagnation = False

    for attempt_no in range(1, max_reproduction_attempts + 1):
        try:
            candidate = generate_reproduction(case, investigation, llm, attempt=attempt_no, feedback=feedback)
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
            consecutive_non_discriminating = 0
            continue
        except LLMError as exc:
            message = f"provider failure: {exc}"
            generation_failures.append(message)
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Reproducer attempt {attempt_no} provider failure: {exc}",
                metadata={"attempt": attempt_no, "usable": False, "provider_error": True, "error": str(exc)},
            ))
            feedback = _generation_feedback(message)
            consecutive_non_discriminating = 0
            continue

        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.GENERATED_TEST,
            summary=f"Reproducer generated attempt {attempt_no}: {candidate.rationale}",
            content=candidate.test_code,
            suffix=".py",
            metadata={"attempt": attempt_no, "rationale": candidate.rationale},
        ))

        original_repro = _run_generated_test(candidate.test_code, case.original_path, timeout_seconds)
        patched_repro: ExecutionResult | None = None
        if not original_repro.passed and not original_repro.timed_out:
            patched_repro = _run_generated_test(candidate.test_code, case.patched_path, timeout_seconds)

        classification, weight = _classify_attempt(original_repro, patched_repro)
        attempt_result = ReproductionAttemptResultV22(
            candidate=candidate,
            original=original_repro,
            patched=patched_repro,
            classification=classification,
            evidence_weight=weight,
        )
        attempts.append(attempt_result)

        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.TEST_RESULT,
            summary=f"reproduction attempt {attempt_no}: {classification.upper()} ({weight} weight)",
            content=(
                _execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / ORIGINAL", original_repro)
                + ("\n" + _execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / PATCHED", patched_repro) if patched_repro else "")
            ),
            metadata={
                "attempt": attempt_no,
                "classification": classification,
                "evidence_weight": weight,
                "original_passed": original_repro.passed,
                "original_timed_out": original_repro.timed_out,
                "patch_passed": None if patched_repro is None else patched_repro.passed,
                "patch_timed_out": None if patched_repro is None else patched_repro.timed_out,
            },
        ))

        if classification == "discriminating":
            discriminating = attempt_result
            break

        if classification == "non_discriminating":
            consecutive_non_discriminating += 1
        else:
            consecutive_non_discriminating = 0

        if consecutive_non_discriminating >= stagnation_limit:
            stopped_for_stagnation = True
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=(
                    f"Reproducer stopped early after {consecutive_non_discriminating} consecutive "
                    "non-discriminating attempts"
                ),
                metadata={"stagnation_limit": stagnation_limit, "stopped_early": True},
            ))
            break

        feedback = _attempt_feedback(classification, original_repro, patched_repro)

    run.advance(RunStage.REPRODUCTION_ATTEMPTED)

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

    run.advance(RunStage.REGRESSION_CHECKED)
    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 2.2 weights only discriminating reproductions as high-confidence evidence",
        metadata={
            "generated_reproduction": True,
            "evidence_weighting": True,
            "stagnation_stop": True,
            "challenger_used": False,
        },
    ))

    reproduction_payload = [
        {
            "attempt": item.candidate.attempt,
            "rationale": item.candidate.rationale,
            "classification": item.classification,
            "evidence_weight": item.evidence_weight,
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
        }
        for item in attempts
    ]

    constraints = _verdict_constraints(patched, discriminating)
    verifier_input = {
        "iteration": "2.2",
        "investigation": investigation.to_dict(),
        "existing_tests": {
            "original": {"passed": original.passed, "exit_code": original.exit_code, "stdout": original.stdout, "stderr": original.stderr},
            "patched": {"passed": patched.passed, "exit_code": patched.exit_code, "stdout": patched.stdout, "stderr": patched.stderr},
        },
        "reproduction_attempts": reproduction_payload,
        "reproduction_generation_failures": generation_failures,
        "discriminating_reproduction_found": discriminating is not None,
        "stopped_for_stagnation": stopped_for_stagnation,
        "evidence_policy": {
            "discriminating": "high-confidence evidence",
            "non_discriminating": "diagnostic-only; cannot establish patch failure",
            "not_reproduced": "no negative evidence against patch",
        },
        "forbidden_verdicts": {verdict.value: reason for verdict, reason in constraints.items()},
        "limitations": ["no challenger-generated nearby cases"],
    }

    raw_verdict = _verifier_complete(
        llm,
        json.dumps(verifier_input, indent=2),
        store,
        run,
        max_attempts=max_provider_attempts,
    )
    proposed_verdict, proposed_reason = _parse_verdict(raw_verdict)
    verdict, reason, gate_overrode_model = _enforce_weighted_gate(
        proposed_verdict, proposed_reason, constraints
    )

    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"evidence-weighted verdict: {verdict.value}",
        content=raw_verdict,
        metadata={
            "proposed_verdict": proposed_verdict.value,
            "final_verdict": verdict.value,
            "reason": reason,
            "evidence_gate_overrode_model": gate_overrode_model,
            "forbidden_verdicts": {v.value: r for v, r in constraints.items()},
        },
    ))
    run.advance(RunStage.COMPLETE)

    counts = {
        name: sum(item.classification == name for item in attempts)
        for name in ("discriminating", "non_discriminating", "not_reproduced")
    }
    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_2_2",
        "iteration": "2.2",
        "verdict": verdict.value,
        "reason": reason,
        "model_proposed_verdict": proposed_verdict.value,
        "model_proposed_reason": proposed_reason,
        "evidence_gate_overrode_model": gate_overrode_model,
        "forbidden_verdicts": {v.value: r for v, r in constraints.items()},
        "stages": run.events,
        "evidence_count": len(run.evidence),
        "reproduction_attempts": len(attempts),
        "reproduction_classifications": counts,
        "reproduction_generation_failures": len(generation_failures),
        "discriminating_reproduction_found": discriminating is not None,
        "stopped_for_stagnation": stopped_for_stagnation,
        "capabilities": {
            "investigator": True,
            "existing_test_execution": True,
            "generated_reproduction": True,
            "bounded_reproduction_retry": True,
            "generation_failure_recovery": True,
            "provider_timeout_recovery": True,
            "deterministic_verdict_gate": True,
            "discriminating_reproduction_semantics": True,
            "evidence_weighting": True,
            "stagnation_stop": True,
            "challenger": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV22(
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
        stopped_for_stagnation=stopped_for_stagnation,
        run_root=store.root,
    )
