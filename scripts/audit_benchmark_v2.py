from __future__ import annotations

import json
import tempfile
from pathlib import Path

from refute.case import load_case
from refute.executor import run_command

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark_v2"
EVAL = ROOT / "eval" / "benchmark_v2"

# Expected public execution shape. Partial/regression cases deliberately look
# repaired on the reported trigger; ineffective cases remain visibly broken.
PUBLIC_SHAPES = {
    "case_001": (False, True),
    "case_002": (False, True),
    "case_003": (False, True),
    "case_004": (False, False),
    "case_005": (False, True),
    "case_006": (False, True),
    "case_007": (False, True),
    "case_008": (False, False),
    "case_009": (False, True),
    "case_010": (True, True),
}

# Whether evaluator-only hidden tests should pass on the patch. A false value
# means the hidden oracle retains behavior not exposed by the public test.
PATCH_HIDDEN_PASS = {
    "case_001": True,
    "case_002": False,
    "case_003": False,
    "case_004": False,
    "case_005": True,
    "case_006": False,
    "case_007": False,
    "case_008": False,
    "case_009": True,
    "case_010": True,
}


def _run_hidden(source: str, repo_root: Path):
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_hidden_oracle.py",
        prefix="test_",
        dir=repo_root,
        encoding="utf-8",
        delete=False,
    ) as handle:
        path = Path(handle.name)
        handle.write(source)
    try:
        return run_command(("python", "-m", "pytest", "-q", path.name), repo_root, 20.0)
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    if not BENCHMARK.is_dir():
        raise SystemExit("benchmark_v2 is not built; run: python scripts/build_benchmark_v2.py")

    hidden = json.loads((EVAL / "hidden_tests.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    for case_id in sorted(PUBLIC_SHAPES):
        case = load_case(BENCHMARK / case_id)
        if case.expected_verdict is not None:
            failures.append(f"{case_id}: public case leaked expected verdict")
            continue

        original = run_command(case.test_command, case.original_path, 20.0)
        patched = run_command(case.test_command, case.patched_path, 20.0)
        expected_original_pass, expected_patch_pass = PUBLIC_SHAPES[case_id]
        if (original.passed, patched.passed) != (expected_original_pass, expected_patch_pass):
            failures.append(
                f"{case_id}: public shape was {(original.passed, patched.passed)}, "
                f"expected {(expected_original_pass, expected_patch_pass)}"
            )

        patched_hidden = _run_hidden(hidden[case_id], case.patched_path)
        if patched_hidden.passed != PATCH_HIDDEN_PASS[case_id]:
            failures.append(
                f"{case_id}: patched hidden result was {patched_hidden.passed}, "
                f"expected {PATCH_HIDDEN_PASS[case_id]}"
            )

        print(
            f"{case_id}: public original={'PASS' if original.passed else 'FAIL'} "
            f"patch={'PASS' if patched.passed else 'FAIL'} | "
            f"hidden patch={'PASS' if patched_hidden.passed else 'FAIL'}"
        )

    if failures:
        print("\nAUDIT FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nAUDIT PASSED: public cases are oracle-free and hidden behavior is separated as designed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
