from __future__ import annotations

import argparse
from pathlib import Path

from .case import CaseFormatError, load_case
from .inspect import inspect_case


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

    return parser


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

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
