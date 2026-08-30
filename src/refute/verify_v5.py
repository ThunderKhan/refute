from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents.probe_compiler_v5 import ContractProbeV5, compile_contract_probes_v5
from .agents.probe_planner_v5 import ProbePlanV5, plan_probes_v5
from .evidence import EvidenceKind, EvidenceStore
from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, Verdict, VerificationCase
from .orchestrator import RunStage, VerificationRun
from .verify_v2 import _execution_text, _run_generated_test
from .verify_v23 import TestDelta, analyze_test_delta
from .verify_v24 import _triage_delta


@dataclass(frozen=True, slots=True)
class ProbeExecutionV5:
    probe: ContractProbeV5
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
class VerificationResultV5:
    run_id: str
    case_id: str
    verdict: Verdict
    reason: str
    original: ExecutionResult
    patched: ExecutionResult
    test_delta: TestDelta
    challenge_executions: tuple[ProbeExecutionV5, ...]
    challenge_generation_failures: tuple[str, ...]
    planner_called: bool
    planner_fallback: bool
    investigator_called: bool
    challenger_called: bool
    critic_called: bool
    verifier_called: bool
    run_root: Path


def _classify(probe: ContractProbeV5, original: ExecutionResult, patched: ExecutionResult) -> str:
    if original.timed_out or patched.timed_out:
        return "invalid_execution"
    if original.exit_code not in {0, 1} or patched.exit_code not in {0, 1}:
        return "invalid_execution"
    if patched.passed:
        return "survived"
    if original.passed:
        return "regression_counterexample"
    if probe.kind == "remaining_requirement" and original.exit_code == 1 and patched.exit_code == 1:
        return "remaining_requirement_counterexample"
    return "non_decisive"


def verify_case_v5(
    case: VerificationCase,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    max_challenge_attempts: int = 2,
    run_id: str | None = None,
) -> VerificationResultV5:
    if max_challenge_attempts < 1:
        raise ValueError("max_challenge_attempts must be at least 1")

    resolved_run_id = run_id or f"{case.case_id}-{uuid.uuid4().hex[:10]}"
    run = VerificationRun(resolved_run_id, case.case_id)
    store = EvidenceStore(artifacts_root, resolved_run_id, case.case_id)
    run.attach(store.record(
        stage=RunStage.LOADED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="case loaded; Iteration 5 compiles public contracts into deterministic probes and uses the agent only to prioritize them",
        metadata={"iteration": "5", "oracle_used": False, "hidden_tests_used": False},
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

    executions: list[ProbeExecutionV5] = []
    failures: list[str] = []
    planner_called = False
    planner_fallback = False
    challenger_called = False
    plan = ProbePlanV5((), "", False)

    if immediate_verdict is not None:
        verdict = immediate_verdict
        reason = immediate_reason or "Deterministic test-first triage resolved the case."
        run.advance(RunStage.REGRESSION_CHECKED)
    elif delta.classification == "suite_repaired" and delta.fixed_tests:
        probes = compile_contract_probes_v5(case)
        challenger_called = True
        planner_called = bool(probes)
        if probes:
            try:
                plan = plan_probes_v5(
                    case,
                    probes,
                    llm,
                    budget=min(max_challenge_attempts, len(probes)),
                )
            except (LLMError, ValueError) as exc:
                failures.append(f"planner failure: {exc}")
                planner_fallback = True
                plan = ProbePlanV5(
                    tuple(probe.probe_id for probe in probes[:max_challenge_attempts]),
                    "",
                    True,
                )

            planner_fallback = planner_fallback or plan.used_fallback
            run.attach(store.record(
                stage=RunStage.CHALLENGED.value,
                kind=EvidenceKind.MODEL_RESPONSE,
                summary=(
                    "probe planner selected: " + ", ".join(plan.selected_ids)
                    if plan.selected_ids else "probe planner produced no selection"
                ),
                content=plan.raw_response or "(deterministic fallback selection)\n",
                suffix=".txt",
                metadata={
                    "available_probe_ids": [probe.probe_id for probe in probes],
                    "selected_probe_ids": list(plan.selected_ids),
                    "fallback": planner_fallback,
                },
            ))

            by_id = {probe.probe_id: probe for probe in probes}
            for probe_id in plan.selected_ids:
                probe = by_id[probe_id]
                original_probe = _run_generated_test(probe.test_code, case.original_path, timeout_seconds)
                patched_probe = _run_generated_test(probe.test_code, case.patched_path, timeout_seconds)
                classification = _classify(probe, original_probe, patched_probe)
                item = ProbeExecutionV5(probe, original_probe, patched_probe, classification)
                executions.append(item)
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.GENERATED_TEST,
                    summary=f"compiled public-contract probe {probe.probe_id}: {probe.description}",
                    content=probe.test_code,
                    suffix=".py",
                    metadata={
                        "probe_id": probe.probe_id,
                        "kind": probe.kind,
                        "contract_id": probe.contract_id,
                        "contract_text": probe.contract_text,
                    },
                ))
                run.attach(store.record(
                    stage=RunStage.CHALLENGED.value,
                    kind=EvidenceKind.TEST_RESULT,
                    summary=f"Iteration 5 probe {probe.probe_id}: {classification}",
                    content=(
                        _execution_text(f"PROBE {probe.probe_id} / ORIGINAL", original_probe)
                        + "\n"
                        + _execution_text(f"PROBE {probe.probe_id} / PATCHED", patched_probe)
                    ),
                    metadata={"probe_id": probe.probe_id, "classification": classification},
                ))
                if item.is_counterexample:
                    break
        else:
            failures.append("no deterministic probes compiled for the public issue contract")

        run.advance(RunStage.CHALLENGED)
        regressions = [x for x in executions if x.classification == "regression_counterexample"]
        remaining = [x for x in executions if x.classification == "remaining_requirement_counterexample"]
        survivors = [x for x in executions if x.classification == "survived"]
        if regressions:
            verdict = Verdict.REGRESSION_INTRODUCED
            reason = "A public-contract-compiled probe passes on the original but fails on the patch, providing executable regression evidence."
        elif remaining:
            verdict = Verdict.PARTIAL_FIX
            reason = "A public-contract-compiled remaining-requirement probe fails on both original and patch after the reported trigger was repaired."
        elif len(survivors) >= 2:
            verdict = Verdict.COMPLETE_FIX
            reason = "The public trigger is repaired and two independent public-contract-compiled probes survive the patch within the bounded budget."
        else:
            verdict = Verdict.INCONCLUSIVE
            reason = "The public trigger is repaired, but Iteration 5 did not collect a counterexample or enough independent survived compiled probes for completeness."
        run.advance(RunStage.REGRESSION_CHECKED)
    else:
        verdict = Verdict.INCONCLUSIVE
        reason = "Public evidence did not establish a repaired trigger, so Iteration 5 did not spend probe-planning budget."
        run.advance(RunStage.REGRESSION_CHECKED)

    run.attach(store.record(
        stage=RunStage.REGRESSION_CHECKED.value,
        kind=EvidenceKind.OBSERVATION,
        summary="Iteration 5 moves executable assertion synthesis out of the language model and into a deterministic public-contract compiler",
        metadata={
            "planner_called": planner_called,
            "planner_fallback": planner_fallback,
            "challenger_called": challenger_called,
            "probe_executions": len(executions),
            "counterexamples": sum(item.is_counterexample for item in executions),
            "generation_failures": len(failures),
            "oracle_used": False,
            "hidden_tests_used": False,
        },
    ))
    run.advance(RunStage.VERDICT_READY)
    run.attach(store.record(
        stage=RunStage.VERDICT_READY.value,
        kind=EvidenceKind.VERDICT,
        summary=f"Iteration 5 verdict: {verdict.value}",
        content=json.dumps({"verdict": verdict.value, "reason": reason}),
    ))
    run.advance(RunStage.COMPLETE)

    manifest = {
        "run_id": resolved_run_id,
        "case_id": case.case_id,
        "mode": "advanced_iteration_5",
        "iteration": "5",
        "verdict": verdict.value,
        "reason": reason,
        "test_delta": delta.classification,
        "planner_called": planner_called,
        "planner_fallback": planner_fallback,
        "challenger_called": challenger_called,
        "challenge_generation_failures": len(failures),
        "challenge_candidates": len(executions),
        "challenge_counterexamples": sum(item.is_counterexample for item in executions),
        "challenge_classifications": [item.classification for item in executions],
        "capabilities": {
            "test_first_routing": True,
            "deterministic_contract_probe_compiler": True,
            "agent_probe_prioritization": True,
            "deterministic_test_compilation": True,
            "deterministic_probe_execution": True,
            "oracle_visible_to_agents": False,
            "hidden_tests_visible_to_agents": False,
        },
    }
    (store.root / "result.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return VerificationResultV5(
        run_id=resolved_run_id,
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        original=original,
        patched=patched,
        test_delta=delta,
        challenge_executions=tuple(executions),
        challenge_generation_failures=tuple(failures),
        planner_called=planner_called,
        planner_fallback=planner_fallback,
        investigator_called=False,
        challenger_called=challenger_called,
        critic_called=False,
        verifier_called=False,
        run_root=store.root,
    )
