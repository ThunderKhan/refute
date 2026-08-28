from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.investigator import Investigation, investigate
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

VERIFIER_SYSTEM_PROMPT = """You are the evidence-constrained verifier in a software patch verification system.
Use only the supplied Investigator hypothesis, existing-test evidence, and generated reproduction evidence.
Do not invent execution facts and do not override explicit tool results.
A generated reproduction is considered successful only when the same test fails on the original and passes on the patched version.
Malformed or timed-out reproduction generations are evidence that reproduction was not established; they are not proof that the patch works or fails.
The input may contain deterministic verdict constraints. You MUST obey them. In particular, if `complete_fix_forbidden_reasons` is non-empty, you must not return `complete_fix`.
This iteration has no Challenger-generated nearby/adversarial tests yet.
Return exactly one JSON object:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief explanation grounded in the supplied evidence"
}
Prefer inconclusive when the evidence cannot distinguish outcomes.
"""


@dataclass(frozen=True, slots=True)
class ReproductionAttemptResult:
    candidate: ReproductionCandidate
    original: ExecutionResult
    patched: ExecutionResult | None
    reproduced: bool
    fixed_by_patch: bool


@dataclass(frozen=True, slots=True)
class VerificationResultV2:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation
    original: ExecutionResult
    patched: ExecutionResult
    reproduction_attempts: tuple[ReproductionAttemptResult, ...]
    successful_reproduction: ReproductionAttemptResult | None
    generation_failures: tuple[str, ...]
    run_root: Path


def _execution_text(label: str, result: ExecutionResult) -> str:
    return (
        f"{label}\n"
        f"command: {' '.join(result.command)}\n"
        f"exit_code: {result.exit_code}\n"
        f"timed_out: {result.timed_out}\n"
        f"duration_seconds: {result.duration_seconds:.6f}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
    )


def _parse_verdict(raw: str) -> tuple[Verdict, str]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            candidate = "\n".join(lines[1:-1])
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:].lstrip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("verifier did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("verifier response must be a JSON object")
    try:
        verdict = Verdict(payload.get("verdict"))
    except (TypeError, ValueError) as exc:
        raise ValueError("verifier returned an invalid verdict") from exc
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("verifier reason must be a non-empty string")
    return verdict, reason.strip()


def _run_generated_test(
    source: str,
    repo_root: Path,
    timeout_seconds: float,
) -> ExecutionResult:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_refute_repro.py",
        prefix="test_",
        dir=repo_root,
        encoding="utf-8",
        delete=False,
    ) as handle:
        path = Path(handle.name)
        handle.write(source)
    try:
        return run_command(
            ("python", "-m", "pytest", "-q", path.name),
            repo_root,
            timeout_seconds,
        )
    finally:
        path.unlink(missing_ok=True)


def _feedback(result: ExecutionResult) -> str:
    return (
        "The prior generated test did NOT reproduce the reported bug on the original. "
        "Revise the reproduction using the execution evidence below.\n\n"
        + _execution_text("PRIOR ORIGINAL REPRODUCTION RUN", result)
    )


def _generation_feedback(error: str) -> str:
    return (
        "The prior reproduction response could not be used: "
        f"{error}. Return ONLY one valid JSON object with string fields `rationale` and `test_code`. "
        "Escape newlines inside test_code as \\n. Do not include markdown fences or commentary."
    )


def _investigate_with_retry(
    case: VerificationCase,
    llm: LLM,
    store: EvidenceStore,
    run: VerificationRun,
    *,
    max_attempts: int,
) -> Investigation:
    last_error: LLMError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return investigate(case, llm)
        except LLMError as exc:
            last_error = exc
            run.attach(store.record(
                stage=RunStage.LOADED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Investigator provider attempt {attempt} failed: {exc}",
                metadata={"attempt": attempt, "component": "investigator", "provider_error": True},
            ))
    assert last_error is not None
    raise LLMError(
        f"investigator failed after {max_attempts} provider attempts: {last_error}"
    ) from last_error


def _verifier_complete_with_retry(
    llm: LLM,
    user_payload: str,
    store: EvidenceStore,
    run: VerificationRun,
    *,
    max_attempts: int,
) -> str:
    last_error: LLMError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm.complete(VERIFIER_SYSTEM_PROMPT, user_payload)
        except LLMError as exc:
            last_error = exc
            run.attach(store.record(
                stage=RunStage.REGRESSION_CHECKED.value,
                kind=EvidenceKind.OBSERVATION,
                summary=f"Verifier provider attempt {attempt} failed: {exc}",
                metadata={"attempt": attempt, "component": "verifier", "provider_error": True},
            ))
    assert last_error is not None
    raise LLMError(
        f"verifier failed after {max_attempts} provider attempts: {last_error}"
    ) from last_error


def _complete_fix_forbidden_reasons(
    patched: ExecutionResult,
    successful_reproduction: ReproductionAttemptResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if patched.timed_out:
        reasons.append("the patched existing test suite timed out")
    elif not patched.passed:
        reasons.append("the patched existing test suite failed")

    if (
        successful_reproduction is not None
        and not successful_reproduction.fixed_by_patch
    ):
        reasons.append(
            "a generated test failed on the original and still failed on the patch"
        )
    return tuple(reasons)


def _enforce_evidence_gate(
    proposed_verdict: Verdict,
    proposed_reason: str,
    forbidden_reasons: tuple[str, ...],
) -> tuple[Verdict, str, bool]:
    if proposed_verdict is not Verdict.COMPLETE_FIX or not forbidden_reasons:
        return proposed_verdict, proposed_reason, False

    reason_text = "; ".join(forbidden_reasons)
    return (
        Verdict.INCONCLUSIVE,
        "Deterministic evidence gate rejected the model's complete_fix verdict because "
        f"{reason_text}. The conflicting evidence must be resolved before the patch can be approved.",
        True,
    )


def verify_case_v2(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_reproduction_attempts: int = 3,
    max_provider_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV2:
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

    attempts: list[ReproductionAttemptResult] = []
    generation_failures: list[str] = []
    successful: ReproductionAttemptResult | None = None
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

        original_repro = _run_generated_test(candidate.test_code, case.original_path, timeout_seconds)
        reproduced = not original_repro.passed and not original_repro.timed_out
        run.attach(store.record(
            stage=RunStage.REPRODUCTION_ATTEMPTED.value,
            kind=EvidenceKind.TEST_RESULT,
            summary=f"reproduction attempt {attempt_no} on original: {'REPRODUCED' if reproduced else 'NOT_REPRODUCED'}",
            content=_execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / ORIGINAL", original_repro),
            metadata={"attempt": attempt_no, "passed": original_repro.passed, "timed_out": original_repro.timed_out},
        ))

        patched_repro: ExecutionResult | None = None
        fixed_by_patch = False
        if reproduced:
            patched_repro = _run_generated_test(candidate.test_code, case.patched_path, timeout_seconds)
            fixed_by_patch = patched_repro.passed
            run.attach(store.record(
                stage=RunStage.REPRODUCTION_ATTEMPTED.value,
                kind=EvidenceKind.TEST_RESULT,
                summary=f"reproduction attempt {attempt_no} on patch: {'PASS' if patched_repro.passed else 'FAIL'}",
                content=_execution_text(f"REPRODUCTION ATTEMPT {attempt_no} / PATCHED", patched_repro),
                metadata={"attempt": attempt_no, "passed": patched_repro.passed, "timed_out": patched_repro.timed_out},
            ))

        attempt_result = ReproductionAttemptResult(
            candidate=candidate,
            original=original_repro,
            patched=patched_repro,
            reproduced=reproduced,
            fixed_by_patch=fixed_by_patch,
        )
        attempts.append(attempt_result)
        if reproduced:
            successful = attempt_result
            break
        feedback = _feedback(original_repro)

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
        summary="Iteration 2 regression signal uses existing tests plus reported-bug reproduction; no Challenger cases yet",
        metadata={"generated_reproduction": True, "challenger_used": False},
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
            "reproduced": item.reproduced,
            "fixed_by_patch": item.fixed_by_patch,
        }
        for item in attempts
    ]

    forbidden_reasons = _complete_fix_forbidden_reasons(patched, successful)
    verifier_input = {
        "investigation": investigation.to_dict(),
        "existing_tests": {
            "original": {"passed": original.passed, "exit_code": original.exit_code, "stdout": original.stdout, "stderr": original.stderr},
            "patched": {"passed": patched.passed, "exit_code": patched.exit_code, "stdout": patched.stdout, "stderr": patched.stderr},
        },
        "reproduction_attempts": reproduction_payload,
        "reproduction_generation_failures": generation_failures,
        "successful_reproduction": successful is not None,
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
        },
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_2",
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
        "successful_reproduction": successful is not None,
        "capabilities": {
            "investigator": True,
            "existing_test_execution": True,
            "generated_reproduction": True,
            "bounded_reproduction_retry": True,
            "generation_failure_recovery": True,
            "provider_timeout_recovery": True,
            "deterministic_verdict_gate": True,
            "challenger": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV2(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        investigation=investigation,
        original=original,
        patched=patched,
        reproduction_attempts=tuple(attempts),
        successful_reproduction=successful,
        generation_failures=tuple(generation_failures),
        run_root=store.root,
    )
