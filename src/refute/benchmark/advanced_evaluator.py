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
from ..verify_v3 import verify_case_v3
from ..verify_v31 import verify_case_v31
from ..verify_v32 import verify_case_v32
from ..verify_v33 import verify_case_v33
from ..verify_v4 import verify_case_v4
from ..verify_v5 import verify_case_v5
from .evaluator import discover_cases
from .oracle import expected_verdict_for_case


CHALLENGER_ITERATIONS = {"3", "3.1", "3.2", "3.3", "4", "5"}


@dataclass(frozen=True, slots=True)
class AdvancedCaseEvaluation:
    case_id: str
    expected: str
    predicted: str
    correct: bool
    runtime_seconds: float
    reason: str
    run_id: str
    challenge_candidates: int = 0
    challenge_counterexamples: int = 0
    challenger_called: bool = False
    challenge_generation_failures: int = 0
    critic_failures: int = 0
    critic_rejections: int = 0
    planner_fallback: bool = False
    error: str | None = None


def _normalize_iteration(iteration: str | int | float) -> str:
    value = str(iteration)
    if value in {"1", "1.0"}:
        return "1"
    if value in {"2", "2.0"}:
        return "2"
    if value in {"2.1", "2.2", "2.3", "2.4", "3", "3.0", "3.1", "3.2", "3.3", "4", "4.0", "5", "5.0"}:
        if value == "3.0":
            return "3"
        if value == "4.0":
            return "4"
        if value == "5.0":
            return "5"
        return value
    raise ValueError("advanced iteration must be 1, 2, 2.1, 2.2, 2.3, 2.4, 3, 3.1, 3.2, 3.3, 4, or 5")


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
    iteration: str | int | float = "5",
    max_reproduction_attempts: int = 3,
    max_challenge_attempts: int = 2,
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
                result = verify_case(case, llm, artifacts_root=artifacts_root, timeout_seconds=timeout_seconds)
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
            elif iteration_name == "2.4":
                result = verify_case_v24(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_reproduction_attempts=min(max_reproduction_attempts, 2),
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "3":
                result = verify_case_v3(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "3.1":
                result = verify_case_v31(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_challenge_attempts=max_challenge_attempts,
                    max_provider_attempts=max_provider_attempts,
                )
            elif iteration_name == "3.2":
                result = verify_case_v32(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_challenge_attempts=max_challenge_attempts,
                )
            elif iteration_name == "3.3":
                result = verify_case_v33(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_challenge_attempts=max_challenge_attempts,
                )
            elif iteration_name == "4":
                result = verify_case_v4(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_challenge_attempts=max_challenge_attempts,
                )
            else:
                result = verify_case_v5(
                    case,
                    llm,
                    artifacts_root=artifacts_root,
                    timeout_seconds=timeout_seconds,
                    max_challenge_attempts=max_challenge_attempts,
                )

            duration = time.perf_counter() - started
            challenge_executions = getattr(result, "challenge_executions", ())
            item = AdvancedCaseEvaluation(
                case_id=case.case_id,
                expected=expected.value,
                predicted=result.verdict.value,
                correct=result.verdict is expected,
                runtime_seconds=duration,
                reason=result.reason,
                run_id=result.run_id,
                challenge_candidates=len(challenge_executions),
                challenge_counterexamples=sum(
                    bool(getattr(entry, "is_counterexample", False)) for entry in challenge_executions
                ),
                challenger_called=bool(getattr(result, "challenger_called", False)),
                challenge_generation_failures=len(
                    getattr(result, "challenge_generation_failures", ())
                ),
                critic_failures=len(getattr(result, "critic_failures", ())),
                critic_rejections=len(getattr(result, "critic_rejections", ())),
                planner_fallback=bool(getattr(result, "planner_fallback", False)),
            )
            if progress:
                marker = "correct" if item.correct else "wrong"
                suffix = ""
                if iteration_name in CHALLENGER_ITERATIONS:
                    suffix = (
                        f", challenges={item.challenge_candidates}, "
                        f"counterexamples={item.challenge_counterexamples}, "
                        f"generation_failures={item.challenge_generation_failures}"
                    )
                    if iteration_name in {"3.3", "4"}:
                        suffix += f", critic_failures={item.critic_failures}"
                    if iteration_name == "4":
                        suffix += f", critic_rejections={item.critic_rejections}"
                    if iteration_name == "5":
                        suffix += f", planner_fallback={'yes' if item.planner_fallback else 'no'}"
                print(f"         {item.predicted} ({marker}, {duration:.2f}s{suffix})", flush=True)
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
        item for item in results
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

    challenged_cases = [
        item for item in results if item.challenger_called and item.error is None
    ]
    challenge_counterexamples = sum(
        item.challenge_counterexamples for item in challenged_cases
    )
    challenger_case_yield = (
        sum(item.challenge_counterexamples > 0 for item in challenged_cases)
        / len(challenged_cases)
        if challenged_cases
        else 0.0
    )
    generated = iteration in {"2", "2.1", "2.2", "2.3", "2.4"}
    capabilities = {
        "investigator": iteration not in {"3.2", "3.3", "4", "5"},
        "existing_test_execution": True,
        "generated_reproduction": generated,
        "test_delta_engine": iteration in {"2.3", "2.4", "3", "3.1", "3.2", "3.3", "4", "5"},
        "test_first_routing": iteration in {"2.4", "3", "3.1", "3.2", "3.3", "4", "5"},
        "challenger": iteration in CHALLENGER_ITERATIONS,
        "grounded_challenger": iteration in {"3.1", "3.2", "3.3", "4", "5"},
        "contract_id_grounding": iteration in {"3.2", "3.3", "4", "5"},
        "deterministic_contract_extraction": iteration in {"3.2", "3.3", "4", "5"},
        "contract_entailment_critic": iteration in {"3.3", "4"},
        "intent_first_challenger": iteration == "4",
        "deterministic_test_compilation": iteration in {"4", "5"},
        "deterministic_contract_probe_compiler": iteration == "5",
        "agent_probe_prioritization": iteration == "5",
    }
    summary = {
        "mode": f"advanced_iteration_{_iteration_slug(iteration)}"
        + ("_benchmark_v2" if oracle_separated else ""),
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
        "false_acceptance_rate": (
            false_accepts / len(non_complete) if non_complete else 0.0
        ),
        "average_runtime_seconds": (
            sum(item.runtime_seconds for item in results) / total if total else 0.0
        ),
        "confusion_matrix": confusion,
        "capabilities": capabilities,
    }
    if iteration in CHALLENGER_ITERATIONS:
        summary.update(
            {
                "challenged_cases": len(challenged_cases),
                "challenge_candidates": sum(
                    item.challenge_candidates for item in challenged_cases
                ),
                "challenge_counterexamples": challenge_counterexamples,
                "challenge_generation_failures": sum(
                    item.challenge_generation_failures for item in challenged_cases
                ),
                "challenger_case_yield": challenger_case_yield,
            }
        )
    if iteration in {"3.3", "4"}:
        summary["critic_failures"] = sum(
            item.critic_failures for item in challenged_cases
        )
    if iteration == "4":
        summary["critic_rejections"] = sum(
            item.critic_rejections for item in challenged_cases
        )
    if iteration == "5":
        summary["planner_fallback_cases"] = sum(
            item.planner_fallback for item in challenged_cases
        )
    return summary


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
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    with (root / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")

    if iteration == "5":
        capability_text = (
            "Deterministic public-contract probe compiler + lightweight agent probe "
            "prioritization + deterministic execution. The model no longer invents "
            "assertions or test code."
        )
    elif iteration == "4":
        capability_text = (
            "Intent-first Challenger: model proposes a typed contract-grounded test "
            "intent, a separate critic validates semantic entailment, and the harness "
            "deterministically compiles and executes pytest code."
        )
    elif iteration == "3.3":
        capability_text = (
            "Contract-id-grounded Challenger plus a separate strict contract-entailment "
            "critic."
        )
    elif iteration == "3.2":
        capability_text = (
            "Deterministic issue-contract extraction + contract-id-grounded Challenger."
        )
    elif iteration == "3.1":
        capability_text = "Grounded Challenger with exact issue-quote validation."
    elif iteration == "3":
        capability_text = (
            "Conditional Challenger-generated nearby falsification executed on original "
            "and patch."
        )
    else:
        capability_text = "Advanced verification iteration."

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
    ]
    if iteration in CHALLENGER_ITERATIONS:
        lines.extend(
            [
                f"- Challenged cases: {summary['challenged_cases']}",
                f"- Challenge candidates: {summary['challenge_candidates']}",
                f"- Challenge counterexamples: {summary['challenge_counterexamples']}",
                f"- Challenge generation failures: {summary['challenge_generation_failures']}",
                f"- Challenger case yield: {summary['challenger_case_yield']:.1%}",
            ]
        )
        if iteration in {"3.3", "4"}:
            lines.append(f"- Challenge critic failures: {summary['critic_failures']}")
        if iteration == "4":
            lines.append(f"- Challenge critic rejections: {summary['critic_rejections']}")
        if iteration == "5":
            lines.append(f"- Planner fallback cases: {summary['planner_fallback_cases']}")
    lines.extend(
        [
            "",
            f"Capabilities: {capability_text}",
            "",
            "| Case | Expected | Predicted | Correct | Runtime | Challenges | Counterexamples | Gen failures | Planner fallback | Run/Error |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in results:
        lines.append(
            f"| {item.case_id} | {item.expected} | {item.predicted} | "
            f"{'yes' if item.correct else 'no'} | {item.runtime_seconds:.2f}s | "
            f"{item.challenge_candidates} | {item.challenge_counterexamples} | "
            f"{item.challenge_generation_failures} | "
            f"{'yes' if item.planner_fallback else 'no'} | {item.error or item.run_id} |"
        )
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
