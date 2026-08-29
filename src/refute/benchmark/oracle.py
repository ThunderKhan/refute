from __future__ import annotations

import json
from pathlib import Path

from ..models import Verdict, VerificationCase


class OracleFormatError(ValueError):
    pass


def load_oracles(oracle_root: str | Path) -> dict[str, Verdict]:
    root = Path(oracle_root).resolve()
    path = root / "oracles.json" if root.is_dir() else root
    if not path.is_file():
        raise OracleFormatError(f"oracle file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OracleFormatError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OracleFormatError("oracle file must contain an object mapping case IDs to verdicts")

    result: dict[str, Verdict] = {}
    for case_id, raw in payload.items():
        if not isinstance(case_id, str) or not case_id.strip():
            raise OracleFormatError("oracle case IDs must be non-empty strings")
        if isinstance(raw, dict):
            raw = raw.get("expected_verdict")
        try:
            result[case_id] = Verdict(raw)
        except (TypeError, ValueError) as exc:
            raise OracleFormatError(f"invalid verdict for {case_id}: {raw!r}") from exc
    return result


def expected_verdict_for_case(
    case: VerificationCase,
    oracle_root: str | Path | None = None,
) -> Verdict:
    if case.expected_verdict is not None:
        return case.expected_verdict
    if oracle_root is None:
        raise OracleFormatError(
            f"case {case.case_id} has no inline oracle; pass an evaluator-only oracle root"
        )
    oracles = load_oracles(oracle_root)
    try:
        return oracles[case.case_id]
    except KeyError as exc:
        raise OracleFormatError(f"missing oracle for case {case.case_id}") from exc
