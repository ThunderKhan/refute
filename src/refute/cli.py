from __future__ import annotations

import argparse
from pathlib import Path

from .baseline import run_baseline
from .benchmark import evaluate_baseline
from .case import CaseFormatError, load_case
from .inspect import inspect_case
from .llm import LLMError, provider_from_env


def _status(result) -> str:
    if result.timed_out:
        return "TIMEOUT"
    return "PASS" if result.passed else f"FAIL (exit {result.exit_code})"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refute",
        description="Evidence-backed verification for software bug-fix patches.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Run the benchmark test command against original and patched code.",
    )
    inspect_parser.add_argument("case_dir", type=Path)
    inspect_parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("artifacts"),
        help="Directory where execution evidence is written.",
    )
    inspect_parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Per-command timeout in seconds.",
    )

    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Run a single static LLM review without executing the repository.",
    )
    baseline_parser.add_argument("case_dir", type=Path)
    _add_provider_args(baseline_parser)
    baseline_parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("artifacts"),
        help="Directory where baseline prompt, response and result are written.",
    )

    eval_parser = subparsers.add_parser(
        "eval-baseline",
        help="Run the static baseline across every case in a benchmark directory.",
    )
    eval_parser.add_argument("benchmark_dir", type=Path)
    _add_provider_args(eval_parser)
    eval_parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("artifacts"),
        help="Directory where per-case and aggregate evaluation evidence is written.",
    )

    return parser


def _add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=("ollama", "openai-compatible"),
        default="ollama",
        help="Language-model provider. Defaults to local Ollama.",
    )
    parser.add_argument(
        "--model",
        help="Model name. May also be supplied with REFUTE_MODEL.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "inspect":
        try:
            case = load_case(args.case_dir)
        except CaseFormatError as exc:
            parser.error(str(exc))

        result = inspect_case(case, args.artifacts, args.timeout)

        print(f"case: {case.case_id}")
        print(f"expected verdict: {case.expected_verdict.value}")
        print()
        print(f"original: {_status(result.original)}")
        print(f"patched:  {_status(result.patched)}")
        print()
        print("execution evidence:")
        for path in result.evidence_paths:
            print(f"  {path}")
        return 0

    if args.command == "baseline":
        try:
            case = load_case(args.case_dir)
            llm = provider_from_env(args.provider, args.model)
            result = run_baseline(case, llm, args.artifacts)
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))

        print(f"case: {case.case_id}")
        print("mode: static baseline (no execution)")
        print(f"verdict: {result.verdict.value}")
        print(f"reason: {result.reason}")
        print()
        print("baseline evidence:")
        print(f"  {result.prompt_path}")
        print(f"  {result.response_path}")
        print(f"  {result.result_path}")
        return 0

    if args.command == "eval-baseline":
        try:
            llm = provider_from_env(args.provider, args.model)
            summary = evaluate_baseline(
                args.benchmark_dir,
                llm,
                artifacts_root=args.artifacts,
                provider_name=args.provider,
                model_name=getattr(llm, "model", args.model or "unknown"),
            )
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))

        print("mode: static baseline benchmark")
        print(f"model: {summary['model']}")
        print(f"cases: {summary['cases']}")
        print(f"verdict accuracy: {summary['verdict_accuracy']:.1%}")
        print(f"false acceptance rate: {summary['false_acceptance_rate']:.1%}")
        print(f"average runtime: {summary['average_runtime_seconds']:.3f}s")
        print()
        print("aggregate evidence:")
        root = args.artifacts.resolve() / "eval" / "baseline"
        print(f"  {root / 'summary.json'}")
        print(f"  {root / 'cases.jsonl'}")
        print(f"  {root / 'report.md'}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
