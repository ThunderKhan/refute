from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.investigator import Investigation, investigate
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun

VERIFIER_SYSTEM_PROMPT = """You are the evidence-constrained verifier in a software patch verification system.
Use the Investigator hypothesis and the deterministic execution evidence supplied to you.
Do not claim evidence that is not present. Do not override explicit execution facts.
This iteration uses existing tests only; no generated reproduction or adversarial tests were attempted.
Return exactly one JSON object:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief explanation grounded in the supplied evidence"
}
If the available evidence cannot distinguish between multiple outcomes, prefer inconclusive.
"""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    investigation: Investigation
    original: ExecutionResult
    patched: ExecutionResult
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


def verify_case(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    run_id: str | None = None,
) -> VerificationResult:
    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)

    inv_prompt_note = store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="verification case loaded; expected benchmark verdict withheld from agents",
    )
    run.attach(inv_prompt_note)

    investigation = investigate(case, llm)
    inv_record = store.record(
        stage=RunStage.INVESTIGATED.value,
        kind=EvidenceKind.MODEL_RESPONSE,
        summary="Investigator produced structured verification hypothesis",
        content=json.dumps(investigation.to_dict(), indent=2) + "\n",
        suffix=".json",
    )
    run.advance(RunStage.INVESTIGATED)
    run.attach(inv_record)

    original = run_command(case.test_command, case.original_path, timeout_seconds)
    original_record = store.record(
        stage=RunStage.ORIGINAL_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on original: {'PASS' if original.passed else 'FAIL'}",
        content=_execution_text("ORIGINAL", original),
        metadata={"exit_code": original.exit_code, "passed": original.passed, "timed_out": original.timed_out},
    )
    run.advance(RunStage.ORIGINAL_VERIFIED)
    run.attach(original_record)

    patched = run_command(case.test_command, case.patched_path, timeout_seconds)
    patched_record = store.record(
        stage=RunStage.PATCH_VERIFIED.value,
        kind=EvidenceKind.TEST_RESULT,
        summary=f"existing tests on patch: {'PASS' if patched.passed else 'FAIL'}",
        content=_execution_text("PATCHED", patched),
        metadata={"exit_code": patched.exit_code, "passed": patched.passed, "timed_out": patched.timed_out},
    )
    run.advance(RunStage.PATCH_VERIFIED)
    run.attach(patched_record)

    run.advance(RunStage.REGRESSION_CHECKED)
    regression_note = store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 1 regression signal is limited to the benchmark's existing test suite",
        metadata={"generated_tests": False, "challenger_used": False},
    )
    run.attach(regression_note)

    verifier_input = {
        "investigation": investigation.to_dict(),
        "execution": {
            "original": {"passed": original.passed, "exit_code": original.exit_code, "timed_out": original.timed_out, "stdout": original.stdout, "stderr": original.stderr},
            "patched": {"passed": patched.passed, "exit_code": patched.exit_code, "timed_out": patched.timed_out, "stdout": patched.stdout, "stderr": patched.stderr},
        },
        "limitations": ["existing tests only", "no generated reproduction", "no challenger cases"],
    }
    raw_verdict = llm.complete(VERIFIER_SYSTEM_PROMPT, json.dumps(verifier_input, indent=2))
    verdict, reason = _parse_verdict(raw_verdict)
    verdict_record = store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"evidence-constrained verdict: {verdict.value}",
        content=raw_verdict,
        metadata={"verdict": verdict.value, "reason": reason},
    )
    run.advance(RunStage.VERDICT_READY)
    run.attach(verdict_record)
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "verdict": verdict.value,
        "reason": reason,
        "stages": run.events,
        "evidence_count": len(run.evidence),
        "capabilities": {"investigator": True, "existing_test_execution": True, "generated_reproduction": False, "challenger": False},
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResult(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        investigation=investigation,
        original=original,
        patched=patched,
        run_root=store.root,
    )
