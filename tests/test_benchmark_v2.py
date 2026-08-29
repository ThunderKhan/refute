from __future__ import annotations

import json
from pathlib import Path

import pytest

from refute.benchmark.evaluator import discover_cases
from refute.benchmark.oracle import OracleFormatError, expected_verdict_for_case
from refute.case import CaseFormatError, load_case
from refute.models import Verdict


def _public_case(tmp_path: Path) -> Path:
    case_dir = tmp_path / "case_001"
    (case_dir / "original").mkdir(parents=True)
    (case_dir / "patched").mkdir()
    (case_dir / "issue.md").write_text("# Bug\n", encoding="utf-8")
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "case_id": "case_001",
                "test_command": ["python", "-m", "pytest", "-q"],
            }
        ),
        encoding="utf-8",
    )
    return case_dir


def test_public_case_withholds_expected_verdict(tmp_path: Path):
    case = load_case(_public_case(tmp_path))
    assert case.expected_verdict is None
    assert case.case_id == "case_001"


def test_public_case_rejects_inline_oracle(tmp_path: Path):
    case_dir = _public_case(tmp_path)
    payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    payload["expected_verdict"] = "complete_fix"
    (case_dir / "case.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CaseFormatError, match="must not contain expected_verdict"):
        load_case(case_dir)


def test_evaluator_resolves_separate_oracle(tmp_path: Path):
    case = load_case(_public_case(tmp_path))
    oracle_root = tmp_path / "oracles"
    oracle_root.mkdir()
    (oracle_root / "oracles.json").write_text(
        json.dumps({"case_001": "partial_fix"}), encoding="utf-8"
    )

    assert expected_verdict_for_case(case, oracle_root) is Verdict.PARTIAL_FIX


def test_public_case_requires_oracle_for_evaluation(tmp_path: Path):
    case = load_case(_public_case(tmp_path))
    with pytest.raises(OracleFormatError, match="pass an evaluator-only oracle root"):
        expected_verdict_for_case(case)


def test_discover_cases_accepts_case_json(tmp_path: Path):
    case_dir = _public_case(tmp_path)
    assert discover_cases(tmp_path) == [case_dir.resolve()]
