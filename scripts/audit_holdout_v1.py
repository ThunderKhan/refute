from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "holdout_v1"
ORACLES = ROOT / "eval" / "holdout_v1" / "oracles.json"


def main() -> int:
    if not HOLDOUT.is_dir():
        raise SystemExit("holdout_v1 is missing; run scripts/build_holdout_v1.py first")
    if not ORACLES.is_file():
        raise SystemExit("eval/holdout_v1/oracles.json is missing")

    oracle_map = json.loads(ORACLES.read_text(encoding="utf-8"))
    if not isinstance(oracle_map, dict):
        raise SystemExit("holdout oracle file must contain a JSON object")

    cases = sorted(path for path in HOLDOUT.glob("holdout_*") if path.is_dir())
    errors: list[str] = []
    digest = hashlib.sha256()

    for case_dir in cases:
        case_id = case_dir.name
        metadata_path = case_dir / "case.json"
        issue_path = case_dir / "issue.md"
        required = [
            metadata_path,
            issue_path,
            case_dir / "original" / "app.py",
            case_dir / "original" / "test_app.py",
            case_dir / "patched" / "app.py",
            case_dir / "patched" / "test_app.py",
        ]
        for path in required:
            if not path.is_file():
                errors.append(f"{case_id}: missing {path.relative_to(HOLDOUT)}")

        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            forbidden = {"expected", "expected_verdict", "oracle", "verdict"}
            leaked = forbidden.intersection(metadata)
            if leaked:
                errors.append(f"{case_id}: forbidden oracle-like keys in public case.json: {sorted(leaked)}")

        public_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in required
            if path.is_file()
        ).casefold()
        if "expected verdict" in public_text and "expected verdict is evaluator-only" not in public_text:
            errors.append(f"{case_id}: suspicious expected-verdict text in public material")

        if case_id not in oracle_map:
            errors.append(f"{case_id}: missing evaluator oracle")

    extra_oracles = sorted(set(oracle_map) - {path.name for path in cases})
    if extra_oracles:
        errors.append(f"oracles without public cases: {extra_oracles}")

    for path in sorted(HOLDOUT.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(HOLDOUT).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")

    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1

    print(f"cases: {len(cases)}")
    print(f"evaluator oracles: {len(oracle_map)}")
    print(f"public holdout sha256: {digest.hexdigest()}")
    print("AUDIT PASSED: holdout public material contains no verdict oracle and case/oracle sets match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
