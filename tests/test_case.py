import json
from pathlib import Path

import pytest

from refute.case import CaseFormatError, load_case
from refute.models import Verdict


def test_load_case_reads_expected_metadata(tmp_path: Path):
    case_dir = tmp_path / "case_x"
    (case_dir / "original").mkdir(parents=True)
    (case_dir / "patched").mkdir()
    (case_dir / "issue.md").write_text("# Bug\n", encoding="utf-8")
    (case_dir / "expected.json").write_text(
        json.dumps(
            {
                "case_id": "case_x",
                "expected_verdict": "complete_fix",
                "test_command": ["python", "-m", "pytest", "-q"],
            }
        ),
        encoding="utf-8",
    )

    case = load_case(case_dir)

    assert case.case_id == "case_x"
    assert case.expected_verdict is Verdict.COMPLETE_FIX
    assert case.test_command == ("python", "-m", "pytest", "-q")
    assert case.issue_text == "# Bug\n"


def test_load_case_rejects_missing_layout(tmp_path: Path):
    case_dir = tmp_path / "broken_case"
    case_dir.mkdir()

    with pytest.raises(CaseFormatError, match="missing required file"):
        load_case(case_dir)
