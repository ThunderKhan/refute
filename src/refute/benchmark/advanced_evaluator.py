from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..case import load_case
from ..llm import LLM, LLMError
from ..models import Verdict
from ..verify import verify_case
from ..verify_v2 import verify_case_v2
from ..verify_v21 import verify_case_v21
from ..verify_v22 import verify_case_v22
from ..verify_v23 import verify_case_v23
from ..verify_v24 import verify_case_v24
from .evaluator import discover_cases
from .oracle import expected_verdict_for_case


@dataclass(frozen=True, slots=True)
class AdvancedCaseEvaluation:
    case_id: str
    expected: str
    predicted: str
    correct: bool
    runtime_seconds: float
    reason: str
    run_id: str
    error: str | None = None


def _normalize_iteration(iteration: str | int | float) -> str:
    value = str(iteration)
    if value in {"1", "1.0"}:
        return "1"
    if value in {"2", "2.0"}:
        return "2"
    if value in {"2.1", "2.2", "2.3", "2.4"}:
        return value
    raise ValueError("advanced iteration must be 1, 2, 2.1, 2.2, 2.3, or 2.4")


def _iteration_slug(iteration: str) -> str:
    return iteration.replace(".", "_")


def _is_oracle_separated(case_dirs: list[Path]) -> bool:
    return bool(case_dirs) and all((case / "case.json").is_file() for case in case_dirs)


def evaluate_advanced(
    benchmark_root: str | Path,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    provider_name: str = "unknown",
    model_name: str = "unknown",
    timeout_seconds: float = 20.0,
    iteration: str | int | float = "2.4",
    max_reproduction_attempts: int = 3,
    max_provider_attempts: int = 1,
    progress: bool = False,
    oracle_root: str | Path | None = None,
) -> dict:
    iteration_name = _normalize_iteration(iteration)
    case_dirs = discover_cases(benchmark_root)
    oracle_separated = _is_oracle_separated(case_dirs)
    results: list[AdvancedCaseEvaluation] = []
    total_cases = len(case_dirs)

    for index, case_dir in enumerate(case_dirs, start=1):
        case = load_case(case_dir)
        expected = expected_verdict_for_case(case, oracle_root)
        if progress:
            print(f"[{index}/{total_cases}] {case.case_id} ...", flush=True)
        started = time.perf_counter()

        try:
            if iteration_name == "1":
                result = verify_case(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                )
            elif iteration_name == "2":
                result = verify_case_v2(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=max_reproduction_attempts,
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "2.1":
                result = verify_case_v21(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=max_reproduction_attempts,
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "2.2":
                result = verify_case_v22(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=max_reproduction_attempts,
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "2.3":
                result = verify_case_v23(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=min(max_reproduction_attempts, 2),
                    max_provider_attempts=max_provider_attempts,
                )
            else:
                result = verify_case_v24(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=min(max_reproduction_attempts, 2),
                    max_provider_attempts=max_provider_attempts,
                )
            duration = time.perf_counter() - started
            item = AdvancedCaseEvaluation(
                case_id=case.case_id,
                expected=expected.value,
                predicted=result.verdict.value,
                correct=result.verdict is expected,
                runtime_seconds=duration,
                reason=result.reason,
                run_id=result.run_id,
            )
            if progress:
                marker = "correct" if item.correct else "wrong"
                print(f"         {item.predicted} ({marker}, {duration:.2f}s)", flush=True)
        except (LLMError, ValueError) as exc:
            duration = time.perf_counter() - started
            item = AdvancedCaseEvaluation(
                case_id=case.case_id,
                expected=expected.value,
                predicted="error",
                correct=False,
                runtime_seconds=duration,
                reason=f"evaluation error: {exc}",
                run_id="error",
                error=str(exc),
            )
            if progress:
                print(f"         ERROR after {duration:.2f}s: {exc}", flush=True)

        results.append(item)
        _write_checkpoint(
            results,
            Path(artifacts_root),
            iteration_name,
            oracle_separated=oracle_separated,
        )

    summary = _summarize(
        results,
        provider_name,
        model_name,
        iteration_name,
        oracle_separated=oracle_separated,
    )
    _write_reports(
        summary,
        results,
        Path(artifacts_root),
        iteration_name,
        oracle_separated=oracle_separated,
    )
    return summary


def _summarize(
    results: list[AdvancedCaseEvaluation],
    provider: str,
    model: str,
    iteration: str,
    *,
    oracle_separated: bool,
) -> dict:
    total = len(results)
    correct = sum(item.correct for item in results)
    errors = sum(item.error is not None for item in results)
    non_complete = [
        item
        for item in results
        if item.error is None and item.expected != Verdict.COMPLETE_FIX.value
    ]
    false_accepts = sum(
        item.predicted == Verdict.COMPLETE_FIX.value for item in non_complete
    )
    confusion = {
        expected.value: {predicted.value: 0 for predicted in Verdict}
        for expected in Verdict
    }
    valid_verdicts = {verdict.value for verdict in Verdict}
    for item in results:
        if item.error is None and item.predicted in valid_verdicts:
            confusion[item.expected][item.predicted] += 1

    generated = iteration in {"2", "2.1", "2.2", "2.3", "2.4"}
    capabilities = {
        "investigator": True,
        "existing_test_execution": True,
        "generated_reproduction": generated,
        "bounded_reproduction_retry": generated,
        "deterministic_verdict_gate": generated,
        "discriminating_reproduction_semantics": iteration in {"2.1", "2.2", "2.3", "2.4"},
        "evidence_weighting": iteration in {"2.2", "2.3", "2.4"},
        "stagnation_stop": iteration == "2.2",
        "test_delta_engine": iteration in {"2.3", "2.4"},
        "conditional_reproduction": iteration in {"2.3", "2.4"},
        "test_first_routing": iteration == "2.4",
        "conditional_investigator": iteration == "2.4",
        "challenger": False,
    }

    return {
        "mode": f"advanced_iteration_{_iteration_slug(iteration)}" + ("_benchmark_v2" if oracle_separated else ""),
        "iteration": iteration,
        "benchmark_oracle_separated": oracle_separated,
        "provider": provider,
        "model": model,
        "cases": total,
        "completed_cases": total - errors,
        "errors": errors,
        "evaluation_complete": errors == 0,
        "correct": correct,
        "verdict_accuracy": correct / total if total else 0.0,
        "false_acceptance_rate": false_accepts / len(non_complete) if non_complete else 0.0,
        "average_runtime_seconds": (
            sum(item.runtime_seconds for item in results) / total if total else 0.0
        ),
        "confusion_matrix": confusion,
        "capabilities": capabilities,
    }


def _root(artifacts_root: Path, iteration: str, *, oracle_separated: bool) -> Path:
    name = f"advanced_iteration_{_iteration_slug(iteration)}"
    if oracle_separated:
        name += "_benchmark_v2"
    root = artifacts_root.resolve() / "eval" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_checkpoint(
    results: list[AdvancedCaseEvaluation],
    artifacts_root: Path,
    iteration: str,
    *,
    oracle_separated: bool,
) -> None:
    root = _root(artifacts_root, iteration, oracle_separated=oracle_separated)
    with (root / "cases.partial.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")


def _write_reports(
    summary: dict,
    results: list[AdvancedCaseEvaluation],
    artifacts_root: Path,
    iteration: str,
    *,
    oracle_separated: bool,
) -> None:
    root = _root(artifacts_root, iteration, oracle_separated=oracle_separated)
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (root / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")

    if iteration == "2.4":
        capability_text = (
            "Deterministic test-first routing + pytest failure-set delta analysis. Investigator, generated reproduction, "
            "and verifier are conditional fallbacks only when deterministic evidence is ambiguous. No Challenger cases."
        )
    elif iteration == "2.3":
        capability_text = (
            "Investigator + deterministic pytest failure-set delta analysis + conditional generated reproduction + "
            "discriminating semantics. No Challenger cases."
        )
    elif iteration == "2.2":
        capability_text = (
            "Investigator + existing-test execution + generated reproduction with bounded retry + "
            "discriminating semantics + confidence weighting + stagnation stop + deterministic verdict gate. No Challenger cases."
        )
    elif iteration == "2.1":
        capability_text = (
            "Investigator + existing-test execution + generated reproduction with bounded retry + "
            "discriminating reproduction semantics + deterministic verdict gate. No Challenger cases."
        )
    elif iteration == "2":
        capability_text = (
            "Investigator + existing-test execution + generated reproduction with bounded retry + deterministic verdict gate. No Challenger cases."
        )
    else:
        capability_text = (
            "Investigator + existing-test execution + evidence-constrained verifier. No generated reproduction or Challenger."
        )

    lines = [
        f"# Advanced Iteration {iteration} Evaluation",
        "",
        f"- Provider: `{summary['provider']}`",
        f"- Model: `{summary['model']}`",
        f"- Cases: {summary['cases']}",
        f"- Oracle separated: {'yes' if summary['benchmark_oracle_separated'] else 'no'}",
        f"- Completed cases: {summary['completed_cases']}",
        f"- Errors: {summary['errors']}",
        f"- Verdict accuracy: {summary['verdict_accuracy']:.1%}",
        f"- False acceptance rate: {summary['false_acceptance_rate']:.1%}",
        f"- Average runtime: {summary['average_runtime_seconds']:.3f}s",
        "",
        f"Capabilities: {capability_text}",
        "",
        "| Case | Expected | Predicted | Correct | Runtime | Run/Error |",
        "|---|---|---|---|---:|---|",
    ]
    for item in results:
        run_or_error = item.error or item.run_id
        lines.append(
            f"| {item.case_id} | {item.expected} | {item.predicted} | "
            f"{'yes' if item.correct else 'no'} | {item.runtime_seconds:.2f}s | {run_or_error} |"
        )
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
