from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..baseline import run_baseline
from ..case import load_case
from ..llm import LLM
from ..models import Verdict
from .oracle import expected_verdict_for_case


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    expected: str
    predicted: str
    correct: bool
    runtime_seconds: float
    reason: str


def discover_cases(root: str | Path) -> list[Path]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"benchmark directory does not exist: {root_path}")
    cases = sorted(
        path
        for path in root_path.iterdir()
        if path.is_dir()
        and ((path / "case.json").is_file() or (path / "expected.json").is_file())
    )
    if not cases:
        raise ValueError(f"no benchmark cases found under: {root_path}")
    return cases


def _is_oracle_separated(cases: list[Path]) -> bool:
    return bool(cases) and all((case / "case.json").is_file() for case in cases)


def evaluate_baseline(
    benchmark_root: str | Path,
    llm: LLM,
    *,
    artifacts_root: str | Path = "artifacts",
    provider_name: str = "unknown",
    model_name: str = "unknown",
    oracle_root: str | Path | None = None,
) -> dict:
    cases = discover_cases(benchmark_root)
    oracle_separated = _is_oracle_separated(cases)
    results: list[CaseEvaluation] = []

    for case_dir in cases:
        case = load_case(case_dir)
        expected = expected_verdict_for_case(case, oracle_root)
        started = time.perf_counter()
        baseline = run_baseline(case, llm, artifacts_root)
        duration = time.perf_counter() - started
        results.append(
            CaseEvaluation(
                case_id=case.case_id,
                expected=expected.value,
                predicted=baseline.verdict.value,
                correct=baseline.verdict is expected,
                runtime_seconds=duration,
                reason=baseline.reason,
            )
        )

    summary = _summarize(
        results,
        provider_name,
        model_name,
        oracle_separated=oracle_separated,
    )
    report_name = "baseline_v2" if oracle_separated else "baseline"
    _write_reports(summary, results, Path(artifacts_root), report_name)
    return summary


def _summarize(
    results: list[CaseEvaluation],
    provider_name: str,
    model_name: str,
    *,
    oracle_separated: bool,
) -> dict:
    total = len(results)
    correct = sum(item.correct for item in results)
    accuracy = correct / total if total else 0.0

    non_complete = [item for item in results if item.expected != Verdict.COMPLETE_FIX.value]
    false_accepts = sum(
        item.predicted == Verdict.COMPLETE_FIX.value for item in non_complete
    )
    false_acceptance_rate = (
        false_accepts / len(non_complete) if non_complete else 0.0
    )

    confusion = {
        expected.value: {predicted.value: 0 for predicted in Verdict}
        for expected in Verdict
    }
    class_counts = {verdict.value: 0 for verdict in Verdict}
    class_correct = {verdict.value: 0 for verdict in Verdict}

    for item in results:
        confusion[item.expected][item.predicted] += 1
        class_counts[item.expected] += 1
        if item.correct:
            class_correct[item.expected] += 1

    per_class_accuracy = {
        verdict: (
            class_correct[verdict] / class_counts[verdict]
            if class_counts[verdict]
            else None
        )
        for verdict in class_counts
    }

    return {
        "mode": "static_baseline_v2" if oracle_separated else "static_baseline",
        "benchmark_oracle_separated": oracle_separated,
        "provider": provider_name,
        "model": model_name,
        "cases": total,
        "correct": correct,
        "verdict_accuracy": accuracy,
        "false_acceptance_rate": false_acceptance_rate,
        "average_runtime_seconds": (
            sum(item.runtime_seconds for item in results) / total if total else 0.0
        ),
        "per_class_accuracy": per_class_accuracy,
        "confusion_matrix": confusion,
    }


def _write_reports(
    summary: dict,
    results: list[CaseEvaluation],
    artifacts_root: Path,
    report_name: str,
) -> None:
    report_root = artifacts_root.resolve() / "eval" / report_name
    report_root.mkdir(parents=True, exist_ok=True)

    (report_root / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with (report_root / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), sort_keys=True) + "\n")

    title = "Baseline v2 Evaluation" if summary["benchmark_oracle_separated"] else "Baseline Evaluation"
    lines = [
        f"# {title}",
        "",
        f"- Provider: `{summary['provider']}`",
        f"- Model: `{summary['model']}`",
        f"- Cases: {summary['cases']}",
        f"- Oracle separated: {'yes' if summary['benchmark_oracle_separated'] else 'no'}",
        f"- Verdict accuracy: {summary['verdict_accuracy']:.1%}",
        f"- False acceptance rate: {summary['false_acceptance_rate']:.1%}",
        f"- Average runtime: {summary['average_runtime_seconds']:.3f}s",
        "",
        "## Cases",
        "",
        "| Case | Expected | Predicted | Correct |",
        "|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item.case_id} | {item.expected} | {item.predicted} | "
            f"{'yes' if item.correct else 'no'} |"
        )
    (report_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
