import json
from pathlib import Path

from refute.benchmark import discover_cases, evaluate_baseline
from refute.llm import LLMError


class CompleteFixLLM:
    def complete(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "verdict": "complete_fix",
                "reason": "fixture model returns a deterministic verdict",
            }
        )


class OneTimeoutLLM:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.calls == 2:
            raise LLMError("timed out")
        return json.dumps(
            {
                "verdict": "complete_fix",
                "reason": "fixture model returns a deterministic verdict",
            }
        )


def _write_case(root: Path, case_id: str, expected: str) -> None:
    case = root / case_id
    (case / "original").mkdir(parents=True)
    (case / "patched").mkdir(parents=True)
    (case / "issue.md").write_text("A tiny issue.\n", encoding="utf-8")
    (case / "original" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (case / "patched" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "case_id": case_id,
                "expected_verdict": expected,
                "test_command": ["python", "-m", "pytest", "-q"],
            }
        ),
        encoding="utf-8",
    )


def test_discover_cases_returns_sorted_case_directories(tmp_path: Path):
    _write_case(tmp_path, "case_002", "partial_fix")
    _write_case(tmp_path, "case_001", "complete_fix")

    assert [path.name for path in discover_cases(tmp_path)] == ["case_001", "case_002"]


def test_evaluator_writes_metrics_and_reports(tmp_path: Path):
    benchmark = tmp_path / "benchmark"
    artifacts = tmp_path / "artifacts"
    _write_case(benchmark, "case_001", "complete_fix")
    _write_case(benchmark, "case_002", "partial_fix")

    summary = evaluate_baseline(
        benchmark,
        CompleteFixLLM(),
        artifacts_root=artifacts,
        provider_name="fake",
        model_name="fixture",
    )

    assert summary["cases"] == 2
    assert summary["completed_cases"] == 2
    assert summary["errors"] == 0
    assert summary["evaluation_complete"] is True
    assert summary["correct"] == 1
    assert summary["verdict_accuracy"] == 0.5
    assert summary["verdict_accuracy_completed_cases"] == 0.5
    assert summary["false_acceptance_rate"] == 1.0

    report_root = artifacts / "eval" / "baseline"
    assert (report_root / "summary.json").is_file()
    assert (report_root / "cases.jsonl").is_file()
    assert (report_root / "report.md").is_file()


def test_evaluator_records_provider_error_and_continues(tmp_path: Path):
    benchmark = tmp_path / "benchmark"
    artifacts = tmp_path / "artifacts"
    _write_case(benchmark, "case_001", "complete_fix")
    _write_case(benchmark, "case_002", "partial_fix")
    _write_case(benchmark, "case_003", "complete_fix")

    summary = evaluate_baseline(
        benchmark,
        OneTimeoutLLM(),
        artifacts_root=artifacts,
        provider_name="fake",
        model_name="fixture",
    )

    assert summary["cases"] == 3
    assert summary["completed_cases"] == 2
    assert summary["errors"] == 1
    assert summary["evaluation_complete"] is False
    assert summary["correct"] == 2
    assert summary["verdict_accuracy"] == 2 / 3
    assert summary["verdict_accuracy_completed_cases"] == 1.0

    rows = [
        json.loads(line)
        for line in (artifacts / "eval" / "baseline" / "cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["predicted"] for row in rows] == ["complete_fix", "error", "complete_fix"]
    assert rows[1]["error"] == "timed out"
