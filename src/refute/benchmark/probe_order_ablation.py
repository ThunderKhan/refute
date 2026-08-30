from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..agents.probe_compiler_v5 import compile_contract_probes_v5
from ..case import load_case
from ..executor import run_command
from ..models import Verdict
from ..verify_v2 import _run_generated_test
from ..verify_v23 import analyze_test_delta
from ..verify_v24 import _triage_delta
from ..verify_v5 import _classify
from .evaluator import discover_cases
from .oracle import expected_verdict_for_case


@dataclass(frozen=True, slots=True)
class AblationCaseResult:
    case_id: str
    expected: str
    predicted: str
    correct: bool
    runtime_seconds: float
    test_delta: str
    compiled_probe_ids: tuple[str, ...]
    selected_probe_ids: tuple[str, ...]
    challenge_classifications: tuple[str, ...]
    challenge_counterexamples: int
    reason: str


def _verdict_from_evidence(delta, executions) -> tuple[Verdict, str]:
    immediate_verdict, immediate_reason = _triage_delta(delta)
    if delta.classification == "suite_repaired":
        immediate_verdict = None
        immediate_reason = None

    if immediate_verdict is not None:
        return immediate_verdict, immediate_reason or "Deterministic test-first triage resolved the case."

    if delta.classification == "suite_repaired" and delta.fixed_tests:
        regressions = [x for x in executions if x[3] == "regression_counterexample"]
        remaining = [x for x in executions if x[3] == "remaining_requirement_counterexample"]
        survivors = [x for x in executions if x[3] == "survived"]
        if regressions:
            return Verdict.REGRESSION_INTRODUCED, "A compiled probe passes on the original but fails on the patch."
        if remaining:
            return Verdict.PARTIAL_FIX, "A compiled remaining-requirement probe fails on both original and patch."
        if len(survivors) >= 2:
            return Verdict.COMPLETE_FIX, "The trigger is repaired and two deterministic-order probes survive."
        return Verdict.INCONCLUSIVE, "The trigger is repaired, but deterministic ordering found neither a counterexample nor two survived probes within budget."

    return Verdict.INCONCLUSIVE, "Public evidence did not establish a repaired trigger."


def evaluate_probe_order_ablation(
    benchmark_root: str | Path,
    *,
    oracle_root: str | Path,
    artifacts_root: str | Path = "artifacts",
    timeout_seconds: float = 20.0,
    probe_budget: int = 2,
    progress: bool = False,
) -> dict:
    if probe_budget < 1:
        raise ValueError("probe_budget must be at least 1")

    cases = discover_cases(benchmark_root)
    results: list[AblationCaseResult] = []

    for index, case_dir in enumerate(cases, start=1):
        case = load_case(case_dir)
        expected = expected_verdict_for_case(case, oracle_root)
        if progress:
            print(f"[{index}/{len(cases)}] {case.case_id} ...", flush=True)
        started = time.perf_counter()

        original = run_command(case.test_command, case.original_path, timeout_seconds)
        patched = run_command(case.test_command, case.patched_path, timeout_seconds)
        delta = analyze_test_delta(original, patched)

        compiled = ()
        selected = ()
        executions: list[tuple[object, object, object, str]] = []

        if delta.classification == "suite_repaired" and delta.fixed_tests:
            compiled = tuple(compile_contract_probes_v5(case))
            selected = compiled[: min(probe_budget, len(compiled))]
            for probe in selected:
                original_probe = _run_generated_test(probe.test_code, case.original_path, timeout_seconds)
                patched_probe = _run_generated_test(probe.test_code, case.patched_path, timeout_seconds)
                classification = _classify(probe, original_probe, patched_probe)
                executions.append((probe, original_probe, patched_probe, classification))
                if classification in {"regression_counterexample", "remaining_requirement_counterexample"}:
                    break

        verdict, reason = _verdict_from_evidence(delta, executions)
        duration = time.perf_counter() - started
        item = AblationCaseResult(
            case_id=case.case_id,
            expected=expected.value,
            predicted=verdict.value,
            correct=verdict is expected,
            runtime_seconds=duration,
            test_delta=delta.classification,
            compiled_probe_ids=tuple(p.probe_id for p in compiled),
            selected_probe_ids=tuple(p.probe_id for p in selected),
            challenge_classifications=tuple(x[3] for x in executions),
            challenge_counterexamples=sum(x[3] in {"regression_counterexample", "remaining_requirement_counterexample"} for x in executions),
            reason=reason,
        )
        results.append(item)
        if progress:
            marker = "correct" if item.correct else "wrong"
            print(
                f"         {item.predicted} ({marker}, {duration:.2f}s, selected={list(item.selected_probe_ids)}, outcomes={list(item.challenge_classifications)})",
                flush=True,
            )

    total = len(results)
    non_complete = [r for r in results if r.expected != Verdict.COMPLETE_FIX.value]
    false_accepts = sum(r.predicted == Verdict.COMPLETE_FIX.value for r in non_complete)
    summary = {
        "mode": "iteration_5_probe_order_ablation",
        "description": "Iteration 5 verdict semantics with the same deterministic compiler and probe budget, but no LLM planner; probes run in compiler order.",
        "cases": total,
        "correct": sum(r.correct for r in results),
        "verdict_accuracy": sum(r.correct for r in results) / total if total else 0.0,
        "false_acceptance_rate": false_accepts / len(non_complete) if non_complete else 0.0,
        "average_runtime_seconds": sum(r.runtime_seconds for r in results) / total if total else 0.0,
        "probe_budget": probe_budget,
        "agent_probe_prioritization": False,
        "deterministic_contract_probe_compiler": True,
        "challenge_counterexamples": sum(r.challenge_counterexamples for r in results),
    }

    root = Path(artifacts_root).resolve() / "eval" / "iteration_5_probe_order_ablation"
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (root / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")

    report = [
        "# Iteration 5 probe-order ablation",
        "",
        summary["description"],
        "",
        f"- cases: {total}",
        f"- accuracy: {summary['verdict_accuracy']:.1%}",
        f"- false acceptance rate: {summary['false_acceptance_rate']:.1%}",
        f"- average runtime: {summary['average_runtime_seconds']:.3f}s",
        f"- probe budget: {probe_budget}",
        f"- counterexamples: {summary['challenge_counterexamples']}",
        "",
        "| case | expected | predicted | correct | selected probes | outcomes |",
        "|---|---|---|---|---|---|",
    ]
    for item in results:
        report.append(
            f"| {item.case_id} | `{item.expected}` | `{item.predicted}` | {'yes' if item.correct else 'no'} | {', '.join(item.selected_probe_ids) or '-'} | {', '.join(item.challenge_classifications) or '-'} |"
        )
    (root / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    summary["artifacts_root"] = str(root)
    return summary
