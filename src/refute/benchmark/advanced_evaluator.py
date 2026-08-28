from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..case import load_case
from ..llm import LLM
from ..models import Verdict
from ..verify import verify_case
from .evaluator import discover_cases


@dataclass(frozen=True, slots=True)
class AdvancedCaseEvaluation:
    case_id: str
    expected: str
    predicted: str
    correct: bool
    runtime_seconds: float
    reason: str
    run_id: str


def evaluate_advanced(
    benchmark_root: str | Path,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    provider_name: str = "unknown",
    model_name: str = "unknown",
    timeout_seconds: float = 20.0,
) -> dict:
    results: list[AdvancedCaseEvaluation] = []
    for case_dir in discover_cases(benchmark_root):
        case = load_case(case_dir)
        started = time.perf_counter()
        result = verify_case(
            case,
            llm,
            artifacts_root=artifacts_root,
            timeout_seconds=timeout_seconds,
        )
        duration = time.perf_counter() - started
        results.append(
            AdvancedCaseEvaluation(
                case_id=case.case_id,
                expected=case.expected_verdict.value,
                predicted=result.verdict.value,
                correct=result.verdict is case.expected_verdict,
                runtime_seconds=duration,
                reason=result.reason,
                run_id=result.run_id,
            )
        )

    summary = _summarize(results, provider_name, model_name)
    _write_reports(summary, results, Path(artifacts_root))
    return summary


def _summarize(results: list[AdvancedCaseEvaluation], provider: str, model: str) -> dict:
    total = len(results)
    correct = sum(item.correct for item in results)
    non_complete = [item for item in results if item.expected != Verdict.COMPLETE_FIX.value]
    false_accepts = sum(item.predicted == Verdict.COMPLETE_FIX.value for item in non_complete)
    confusion = {
        expected.value: {predicted.value: 0 for predicted in Verdict}
        for expected in Verdict
    }
    for item in results:
        confusion[item.expected][item.predicted] += 1
    return {
        "mode": "advanced_iteration_1",
        "provider": provider,
        "model": model,
        "cases": total,
        "correct": correct,
        "verdict_accuracy": correct / total if total else 0.0,
        "false_acceptance_rate": false_accepts / len(non_complete) if non_complete else 0.0,
        "average_runtime_seconds": sum(item.runtime_seconds for item in results) / total if total else 0.0,
        "confusion_matrix": confusion,
        "capabilities": {
            "investigator": True,
            "existing_test_execution": True,
            "generated_reproduction": False,
            "challenger": False,
        },
    }


def _write_reports(summary: dict, results: list[AdvancedCaseEvaluation], artifacts_root: Path) -> None:
    root = artifacts_root.resolve() / "eval" / "advanced_iteration_1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (root / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")
    lines = [
        "# Advanced Iteration 1 Evaluation",
        "",
        f"- Provider: `{summary['provider']}`",
        f"- Model: `{summary['model']}`",
        f"- Cases: {summary['cases']}",
        f"- Verdict accuracy: {summary['verdict_accuracy']:.1%}",
        f"- False acceptance rate: {summary['false_acceptance_rate']:.1%}",
        f"- Average runtime: {summary['average_runtime_seconds']:.3f}s",
        "",
        "Capabilities: Investigator + existing-test execution + evidence-constrained verifier. No generated reproduction or challenger.",
        "",
        "| Case | Expected | Predicted | Correct | Run |",
        "|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(f"| {item.case_id} | {item.expected} | {item.predicted} | {'yes' if item.correct else 'no'} | {item.run_id} |")
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
