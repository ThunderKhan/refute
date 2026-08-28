from __future__ import annotations

import json
import re
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


VERIFIER_SYSTEM_PROMPT_V23 = """You are the semantic verifier in a software patch verification system.
Deterministic test-delta evidence has already been computed for you and takes precedence over model intuition.

Rules:
- Never contradict deterministic suite transitions or explicit generated-test execution.
- `deterministic_verdict` is authoritative when present.
- Existing test identifiers are mechanically compared between original and patch.
- A generated reproduction is high-confidence only when it fails on original and passes on patch.
- Non-discriminating or not-reproduced generated tests cannot establish patch failure.
- If deterministic evidence is ambiguous, use the Investigator hypothesis and high-confidence reproduction only.
- Prefer inconclusive when ambiguity remains.

Return exactly one JSON object:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief explanation grounded in supplied evidence"
}
"""

_FAILED_RE = re.compile(r"^FAILED\s+([^\s]+::[^\s]+)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class TestDelta:
    original_failures: tuple[str, ...]
    patched_failures: tuple[str, ...]
    fixed_tests: tuple[str, ...]
    remaining_failures: tuple[str, ...]
    new_failures: tuple[str, ...]
    classification: str
    deterministic_verdict: Verdict | None
    reason: str


@dataclass(frozen=True, slots=True)
class VerificationResultV23:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    reproduction_attempts: tuple[ReproductionAttemptResultV22, ...]
    discriminating_reproduction: ReproductionAttemptResultV22 | None
    generation_failures: tuple[str, ...]
    verifier_called: bool
    run_root: Path


def _failure_ids(result: ExecutionResult) -> tuple[str, ...]:
    text = result.stdout + "\n" + result.stderr
    return tuple(sorted(set(_FAILED_RE.findall(text))))


def analyze_test_delta(original: ExecutionResult, patched: ExecutionResult) -> TestDelta:
    original_ids = set(_failure_ids(original))
    patched_ids = set(_failure_ids(patched))
    fixed = tuple(sorted(original_ids - patched_ids))
    remaining = tuple(sorted(original_ids & patched_ids))
    new = tuple(sorted(patched_ids - original_ids))

    if patched.timed_out:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "patch_timeout", None,
            "patched test suite timed out, so the observed outcome is inconclusive",
        )

    if original.timed_out:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "original_timeout", None,
            "original test suite timed out, so a reliable before/after delta cannot be established",
        )

    # Strongest signal: tests that did not fail before now fail after the patch.
    if new:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "new_regressions", Verdict.REGRESSION_INTRODUCED,
            f"patch introduces {len(new)} newly failing test(s) that did not fail on the original",
        )

    # All observed failures were removed and the patch suite is clean.
    if not original.passed and patched.passed:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "suite_repaired", None,
            "original suite failed and patched suite passes; observed failures are repaired, but semantic completeness still needs confirmation",
        )

    # Some observed failures were fixed, but others remain.
    if fixed and not patched.passed:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "partial_progress", Verdict.PARTIAL_FIX,
            f"patch fixes {len(fixed)} previously failing test(s) while {len(remaining)} observed failure(s) remain",
        )

    # Same named failures persist with no observed improvement.
    if (
        not original.passed
        and not patched.passed
        and original_ids
        and patched_ids
        and original_ids == patched_ids
    ):
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "no_observed_progress", Verdict.INEFFECTIVE_FIX,
            "the same observed test failures persist after the patch with no fixed or newly failing tests",
        )

    # If pytest output is unavailable or IDs cannot be parsed, retain execution facts but do not fabricate a label.
    if original.passed and not patched.passed:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "patch_breaks_suite", Verdict.REGRESSION_INTRODUCED,
            "original suite passes while patched suite fails",
        )

    if original.passed and patched.passed:
        return TestDelta(
            tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
            "both_pass", None,
            "both existing suites pass, so the reported issue is not distinguished by existing tests",
        )

    return TestDelta(
        tuple(sorted(original_ids)), tuple(sorted(patched_ids)), fixed, remaining, new,
        "ambiguous_failure_delta", None,
        "both suites fail but their pytest failure identifiers do not support a deterministic verdict",
    )


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
            return llm.complete(VERIFIER_SYSTEM_PROMPT_V23, payload)
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


def _reproduction_needed(delta: TestDelta) -> bool:
    # Deterministic test deltas already expose partial/ineffective/regression outcomes.
    # Reproduction is most valuable when the visible suite looks repaired or cannot distinguish the issue.
    return delta.deterministic_verdict is None


def verify_case_v23(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_reproduction_attempts: int = 2,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV23:
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
        metadata={"iteration": "2.3"},
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

    # Iteration 2.3 moves cheap deterministic evidence ahead of expensive reproduction.
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

    attempts: list[ReproductionAttemptResultV22] = []
    generation_failures: list[str] = []
    discriminating: ReproductionAttemptResultV22 | None = None
    feedback: str | None = None

    if _reproduction_needed(delta):
        for attempt_no in range(1, max_reproduction_attempts + 1):
            try:
                candidate = generate_reproduction(case, investigation, llm, attempt=attempt_no, feedback=feedback)
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

            original_repro = _run_generated_test(candidate.test_code, case.original_path, timeout_seconds)
            patched_repro: ExecutionResult | None = None
            if not original_repro.passed and not original_repro.timed_out:
                patched_repro = _run_generated_test(candidate.test_code, case.patched_path, timeout_seconds)
            classification, weight = _classify_attempt(original_repro, patched_repro)
            item = ReproductionAttemptResultV22(candidate, original_repro, patched_repro, classification, weight)
            attempts.append(item)
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"reproduction attempt {attempt_no}: {classification.upper()} ({weight} weight)",
                content=(
                    _execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / ORIGINAL", original_repro)
                    + ("\n" + _execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / PATCHED", patched_repro) if patched_repro else "")
                ),
                metadata={"attempt": attempt_no, "classification": classification, "evidence_weight": weight},
            ))
            if classification == "discriminating":
                discriminating = item
                break
            feedback = _non_discriminating_feedback(original_repro, patched_repro)

    run.advance(RunStage.REPRODUCTION_ATTEMPTED)
    run.advance(RunStage.REGRESSION_CHECKED)
    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 2.3 uses deterministic pytest failure-set deltas before conditional generated reproduction",
        metadata={
            "test_delta_engine": True,
            "conditional_reproduction": True,
            "reproduction_needed": _reproduction_needed(delta),
            "challenger_used": False,
        },
    ))

    verifier_called = False
    if delta.deterministic_verdict is not None:
        verdict = delta.deterministic_verdict
        reason = f"Deterministic test-delta engine: {delta.reason}."
        raw_verdict = json.dumps({"verdict": verdict.value, "reason": reason})
    else:
        verifier_called = True
        payload = {
            "iteration": "2.3",
            "investigation": investigation.to_dict(),
            "test_delta": {
                "classification": delta.classification,
                "reason": delta.reason,
                "fixed_tests": delta.fixed_tests,
                "remaining_failures": delta.remaining_failures,
                "new_failures": delta.new_failures,
                "deterministic_verdict": None,
            },
            "existing_tests": {
                "original": {"passed": original.passed, "exit_code": original.exit_code},
                "patched": {"passed": patched.passed, "exit_code": patched.exit_code},
            },
            "reproduction_attempts": [
                {"classification": item.classification, "evidence_weight": item.evidence_weight}
                for item in attempts
            ],
            "discriminating_reproduction_found": discriminating is not None,
            "limitations": ["no Challenger-generated nearby cases"],
        }
        raw_verdict = _verifier_complete(
            llm, json.dumps(payload, indent=2), store, run, max_attempts=max_provider_attempts
        )
        verdict, reason = _parse_verdict(raw_verdict)

        # Observed-suite repair is strong positive evidence. Diagnostic generated tests may not downgrade it.
        if delta.classification == "suite_repaired" and discriminating is None and verdict in {
            Verdict.PARTIAL_FIX, Verdict.INEFFECTIVE_FIX, Verdict.REGRESSION_INTRODUCED
        }:
            verdict = Verdict.INCONCLUSIVE
            reason = (
                "Deterministic gate rejected a negative verdict because the existing suite is fully repaired and "
                "no high-confidence generated reproduction established a remaining or regressed behavior."
            )

    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 2.3 verdict: {verdict.value}",
        content=raw_verdict,
        metadata={
            "final_verdict": verdict.value,
            "reason": reason,
            "test_delta_classification": delta.classification,
            "deterministic_verdict": None if delta.deterministic_verdict is None else delta.deterministic_verdict.value,
            "verifier_called": verifier_called,
        },
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_2_3",
        "iteration": "2.3",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": {
            "classification": delta.classification,
            "deterministic_verdict": None if delta.deterministic_verdict is None else delta.deterministic_verdict.value,
            "fixed_tests": list(delta.fixed_tests),
            "remaining_failures": list(delta.remaining_failures),
            "new_failures": list(delta.new_failures),
        },
        "reproduction_attempts": len(attempts),
        "reproduction_generation_failures": len(generation_failures),
        "discriminating_reproduction_found": discriminating is not None,
        "verifier_called": verifier_called,
        "capabilities": {
            "investigator": True,
            "existing_test_execution": True,
            "test_delta_engine": True,
            "conditional_generated_reproduction": True,
            "discriminating_reproduction_semantics": True,
            "deterministic_verdicts_for_observed_test_deltas": True,
            "challenger": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV23(
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
        verifier_called=verifier_called,
        run_root=store.root,
    )
