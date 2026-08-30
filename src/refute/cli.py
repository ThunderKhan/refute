from __future__ import annotations

import argparse
from pathlib import Path

from .baseline import run_baseline
from .benchmark import evaluate_baseline
from .benchmark.advanced_evaluator import evaluate_advanced
from .case import CaseFormatError, load_case
from .inspect import inspect_case
from .llm import LLMError, provider_from_env
from .verify import verify_case
from .verify_v2 import verify_case_v2
from .verify_v21 import verify_case_v21
from .verify_v22 import verify_case_v22
from .verify_v23 import verify_case_v23
from .verify_v24 import verify_case_v24
from .verify_v3 import verify_case_v3
from .verify_v31 import verify_case_v31
from .verify_v32 import verify_case_v32
from .verify_v33 import verify_case_v33
from .verify_v4 import verify_case_v4


def _status(result) -> str:
    if result.timed_out:
        return "TIMEOUT"
    return "PASS" if result.passed else f"FAIL (exit {result.exit_code})"


def _iteration_slug(iteration: str) -> str:
    return iteration.replace(".", "_")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="refute", description="Evidence-backed verification for software bug-fix patches.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Run the benchmark test command against original and patched code.")
    inspect_parser.add_argument("case_dir", type=Path)
    inspect_parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    inspect_parser.add_argument("--timeout", type=float, default=20.0)

    baseline_parser = subparsers.add_parser("baseline", help="Run a single static LLM review without executing the repository.")
    baseline_parser.add_argument("case_dir", type=Path)
    _add_provider_args(baseline_parser)
    baseline_parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))

    eval_parser = subparsers.add_parser("eval-baseline", help="Run the static baseline across every case in a benchmark directory.")
    eval_parser.add_argument("benchmark_dir", type=Path)
    _add_provider_args(eval_parser)
    eval_parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    eval_parser.add_argument("--oracle-root", type=Path, default=None, help="Evaluator-only oracle directory/file for oracle-separated cases.")

    iterations = ("1", "2", "2.1", "2.2", "2.3", "2.4", "3", "3.1", "3.2", "3.3", "4")

    verify_parser = subparsers.add_parser("verify", help="Run an advanced verification iteration. Defaults to Iteration 4.")
    verify_parser.add_argument("case_dir", type=Path)
    _add_provider_args(verify_parser)
    verify_parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    verify_parser.add_argument("--timeout", type=float, default=20.0)
    verify_parser.add_argument("--iteration", choices=iterations, default="4")
    verify_parser.add_argument("--max-reproduction-attempts", type=int, default=3)
    verify_parser.add_argument("--max-challenge-attempts", type=int, default=2)

    advanced_parser = subparsers.add_parser("eval-advanced", help="Evaluate an advanced verification iteration over a benchmark directory.")
    advanced_parser.add_argument("benchmark_dir", type=Path)
    _add_provider_args(advanced_parser)
    advanced_parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    advanced_parser.add_argument("--timeout", type=float, default=20.0)
    advanced_parser.add_argument("--iteration", choices=iterations, default="4")
    advanced_parser.add_argument("--max-reproduction-attempts", type=int, default=3)
    advanced_parser.add_argument("--max-challenge-attempts", type=int, default=2)
    advanced_parser.add_argument("--oracle-root", type=Path, default=None, help="Evaluator-only oracle directory/file for oracle-separated cases.")
    return parser


def _add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=("ollama", "openai-compatible"), default="ollama")
    parser.add_argument("--model", help="Model name. May also be supplied with REFUTE_MODEL.")
    parser.add_argument("--llm-timeout", type=float, default=30.0)


def _provider(args):
    return provider_from_env(args.provider, args.model, timeout_seconds=args.llm_timeout)


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
        print("expected verdict: " + (case.expected_verdict.value if case.expected_verdict is not None else "withheld from public case"))
        print()
        print(f"original: {_status(result.original)}")
        print(f"patched:  {_status(result.patched)}")
        print("execution evidence:")
        for path in result.evidence_paths:
            print(f"  {path}")
        return 0

    if args.command == "baseline":
        try:
            case = load_case(args.case_dir)
            llm = _provider(args)
            result = run_baseline(case, llm, args.artifacts)
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))
        print(f"case: {case.case_id}")
        print("mode: static baseline (no execution)")
        print(f"verdict: {result.verdict.value}")
        print(f"reason: {result.reason}")
        print(f"baseline evidence:\n  {result.prompt_path}\n  {result.response_path}\n  {result.result_path}")
        return 0

    if args.command == "eval-baseline":
        try:
            llm = _provider(args)
            summary = evaluate_baseline(args.benchmark_dir, llm, artifacts_root=args.artifacts, provider_name=args.provider, model_name=getattr(llm, "model", args.model or "unknown"), oracle_root=args.oracle_root)
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))
        oracle_separated = summary.get("benchmark_oracle_separated", False)
        print("mode: " + ("static baseline v2 benchmark" if oracle_separated else "static baseline benchmark"))
        print(f"model: {summary['model']}\ncases: {summary['cases']}\noracle separated: {'yes' if oracle_separated else 'no'}")
        print(f"verdict accuracy: {summary['verdict_accuracy']:.1%}\nfalse acceptance rate: {summary['false_acceptance_rate']:.1%}\naverage runtime: {summary['average_runtime_seconds']:.3f}s")
        report_name = "baseline_v2" if oracle_separated else "baseline"
        root = args.artifacts.resolve() / "eval" / report_name
        print(f"aggregate evidence:\n  {root / 'summary.json'}\n  {root / 'cases.jsonl'}\n  {root / 'report.md'}")
        return 0

    if args.command == "verify":
        try:
            case = load_case(args.case_dir)
            llm = _provider(args)
            if args.iteration == "1":
                result = verify_case(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout)
            elif args.iteration == "2":
                result = verify_case_v2(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_reproduction_attempts=args.max_reproduction_attempts)
            elif args.iteration == "2.1":
                result = verify_case_v21(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_reproduction_attempts=args.max_reproduction_attempts)
            elif args.iteration == "2.2":
                result = verify_case_v22(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_reproduction_attempts=args.max_reproduction_attempts)
            elif args.iteration == "2.3":
                result = verify_case_v23(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_reproduction_attempts=min(args.max_reproduction_attempts, 2))
            elif args.iteration == "2.4":
                result = verify_case_v24(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_reproduction_attempts=min(args.max_reproduction_attempts, 2))
            elif args.iteration == "3":
                result = verify_case_v3(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout)
            elif args.iteration == "3.1":
                result = verify_case_v31(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_challenge_attempts=args.max_challenge_attempts)
            elif args.iteration == "3.2":
                result = verify_case_v32(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_challenge_attempts=args.max_challenge_attempts)
            elif args.iteration == "3.3":
                result = verify_case_v33(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_challenge_attempts=args.max_challenge_attempts)
            else:
                result = verify_case_v4(case, llm, artifacts_root=args.artifacts, timeout_seconds=args.timeout, max_challenge_attempts=args.max_challenge_attempts)
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))

        print(f"case: {case.case_id}\nmode: advanced iteration {args.iteration}\nrun: {result.run_id}")
        print(f"original tests: {_status(result.original)}\npatched tests:  {_status(result.patched)}")
        if args.iteration in {"2.3", "2.4"}:
            print(f"test delta: {result.test_delta.classification}")
            print(f"observed failures: fixed={len(result.test_delta.fixed_tests)} remaining={len(result.test_delta.remaining_failures)} new={len(result.test_delta.new_failures)}")
            print(f"reproduction attempts: {len(result.reproduction_attempts)}")
            print("discriminating reproduction found: " + ("yes" if result.discriminating_reproduction is not None else "no"))
            if args.iteration == "2.4":
                print("investigator called: " + ("yes" if result.investigator_called else "no"))
            print("semantic verifier called: " + ("yes" if result.verifier_called else "no"))
        elif args.iteration in {"3", "3.1", "3.2", "3.3", "4"}:
            print(f"test delta: {result.test_delta.classification}")
            print("investigator called: " + ("yes" if result.investigator_called else "no"))
            print("challenger called: " + ("yes" if result.challenger_called else "no"))
            print(f"challenge candidates executed: {len(result.challenge_executions)}")
            print("challenge counterexamples: " + str(sum(item.is_counterexample for item in result.challenge_executions)))
            if args.iteration in {"3.1", "3.2", "3.3", "4"}:
                print(f"challenge generation failures: {len(result.challenge_generation_failures)}")
            if args.iteration in {"3.3", "4"}:
                print("challenge critic called: " + ("yes" if result.critic_called else "no"))
                print(f"challenge critic failures: {len(result.critic_failures)}")
            if args.iteration == "4":
                print(f"challenge critic rejections: {len(result.critic_rejections)}")
            if result.challenge_executions:
                print("challenge outcomes: " + ", ".join(item.classification for item in result.challenge_executions))
            print("semantic verifier called: " + ("yes" if result.verifier_called else "no"))
        elif args.iteration in {"2", "2.1", "2.2"}:
            print(f"reproduction attempts: {len(result.reproduction_attempts)}")
        print(f"verdict: {result.verdict.value}\nreason: {result.reason}\nevidence: {result.run_root}")
        return 0

    if args.command == "eval-advanced":
        try:
            llm = _provider(args)
            summary = evaluate_advanced(args.benchmark_dir, llm, artifacts_root=args.artifacts, provider_name=args.provider, model_name=getattr(llm, "model", args.model or "unknown"), timeout_seconds=args.timeout, iteration=args.iteration, max_reproduction_attempts=args.max_reproduction_attempts, max_challenge_attempts=args.max_challenge_attempts, max_provider_attempts=1, progress=True, oracle_root=args.oracle_root)
        except (CaseFormatError, LLMError, ValueError) as exc:
            parser.error(str(exc))
        oracle_separated = summary.get("benchmark_oracle_separated", False)
        print(f"\nmode: advanced iteration {args.iteration} benchmark" + (" v2" if oracle_separated else ""))
        print(f"model: {summary['model']}\ncases: {summary['cases']}\noracle separated: {'yes' if oracle_separated else 'no'}\ncompleted cases: {summary['completed_cases']}\nerrors: {summary['errors']}")
        print(f"verdict accuracy: {summary['verdict_accuracy']:.1%}\nfalse acceptance rate: {summary['false_acceptance_rate']:.1%}")
        if "challenger_case_yield" in summary:
            print(f"challenger case yield: {summary['challenger_case_yield']:.1%}\nchallenge counterexamples: {summary['challenge_counterexamples']}")
            if "challenge_generation_failures" in summary:
                print(f"challenge generation failures: {summary['challenge_generation_failures']}")
            if "critic_failures" in summary:
                print(f"challenge critic failures: {summary['critic_failures']}")
            if "critic_rejections" in summary:
                print(f"challenge critic rejections: {summary['critic_rejections']}")
        print(f"average runtime: {summary['average_runtime_seconds']:.3f}s")
        if not summary["evaluation_complete"]:
            print("warning: evaluation contains provider/validation errors; inspect the report before comparing metrics")
        name = f"advanced_iteration_{_iteration_slug(args.iteration)}" + ("_benchmark_v2" if oracle_separated else "")
        root = args.artifacts.resolve() / "eval" / name
        print(f"aggregate evidence:\n  {root / 'summary.json'}\n  {root / 'cases.jsonl'}\n  {root / 'report.md'}\n  {root / 'cases.partial.jsonl'}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
