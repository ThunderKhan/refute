from __future__ import annotations

import json
from pathlib import Path

from refute.agents.challenger_v31 import ChallengeGenerationErrorV31, generate_challenge_v31
from refute.case import load_case
from refute.models import Verdict
from refute.verify_v31 import verify_case_v31


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _investigation() -> str:
    return json.dumps({
        "expected_behavior": "0 through 100 inclusive are valid",
        "reported_failure": "zero fails",
        "trigger_conditions": ["zero"],
        "likely_files": ["app.py"],
        "reproduction_strategy": "exercise boundary",
        "risk_areas": ["upper boundary"],
    })


def _case(tmp_path: Path):
    root = tmp_path / "case_x"
    for name, app in (
        ("original", "def f(x):\n    if x <= 0 or x >= 100: raise ValueError\n    return x\n"),
        ("patched", "def f(x):\n    if x < 0 or x >= 100: raise ValueError\n    return x\n"),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "app.py").write_text(app, encoding="utf-8")
        (d / "test_app.py").write_text("from app import f\n\ndef test_zero():\n    assert f(0) == 0\n", encoding="utf-8")
    (root / "issue.md").write_text("Values from 0 through 100 inclusive are valid; zero is currently rejected.\n", encoding="utf-8")
    (root / "case.json").write_text(json.dumps({"case_id": "case_x", "test_command": ["python", "-m", "pytest", "-q"]}), encoding="utf-8")
    return load_case(root)


def test_grounding_quote_must_come_from_issue(tmp_path: Path):
    case = _case(tmp_path)
    from refute.agents.investigator import parse_investigation
    investigation = parse_investigation(_investigation())
    llm = SequencedLLM([json.dumps({
        "kind": "remaining_requirement",
        "grounding_quote": "this quote is invented",
        "rationale": "upper boundary",
        "test_code": "from app import f\n\ndef test_upper():\n    assert f(100) == 100\n",
    })])
    try:
        generate_challenge_v31(case, investigation, llm, attempt=1)
    except ChallengeGenerationErrorV31:
        pass
    else:
        raise AssertionError("invented grounding quote should be rejected")


def test_v31_grounded_remaining_requirement_finds_partial(tmp_path: Path):
    case = _case(tmp_path)
    challenger = json.dumps({
        "kind": "remaining_requirement",
        "grounding_quote": "0 through 100 inclusive",
        "rationale": "upper boundary remains part of the explicit inclusive range",
        "test_code": "from app import f\n\ndef test_upper():\n    assert f(100) == 100\n",
    })
    result = verify_case_v31(
        case,
        SequencedLLM([_investigation(), challenger]),
        artifacts_root=tmp_path / "artifacts",
        timeout_seconds=10,
    )
    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.challenge_executions[0].classification == "remaining_requirement_counterexample"


def test_v31_survived_grounded_challenges_can_support_complete(tmp_path: Path):
    root = tmp_path / "complete"
    for name, app in (
        ("original", "def f(x):\n    if x <= 0 or x > 100: raise ValueError\n    return x\n"),
        ("patched", "def f(x):\n    if x < 0 or x > 100: raise ValueError\n    return x\n"),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "app.py").write_text(app, encoding="utf-8")
        (d / "test_app.py").write_text("from app import f\n\ndef test_zero():\n    assert f(0) == 0\n", encoding="utf-8")
    (root / "issue.md").write_text("Accept every integer from 0 through 100 inclusive. Zero is currently rejected.\n", encoding="utf-8")
    (root / "case.json").write_text(json.dumps({"case_id": "complete", "test_command": ["python", "-m", "pytest", "-q"]}), encoding="utf-8")
    case = load_case(root)
    investigation = json.dumps({
        "expected_behavior": "inclusive range",
        "reported_failure": "zero fails",
        "trigger_conditions": ["zero"],
        "likely_files": ["app.py"],
        "reproduction_strategy": "boundary",
        "risk_areas": ["upper boundary"],
    })
    challenge1 = json.dumps({
        "kind": "remaining_requirement",
        "grounding_quote": "0 through 100 inclusive",
        "rationale": "check upper boundary",
        "test_code": "from app import f\n\ndef test_upper():\n    assert f(100) == 100\n",
    })
    challenge2 = json.dumps({
        "kind": "remaining_requirement",
        "grounding_quote": "0 through 100 inclusive",
        "rationale": "check nearby interior",
        "test_code": "from app import f\n\ndef test_mid():\n    assert f(99) == 99\n",
    })
    result = verify_case_v31(case, SequencedLLM([investigation, challenge1, challenge2]), artifacts_root=tmp_path / "artifacts2", timeout_seconds=10)
    assert result.verdict is Verdict.COMPLETE_FIX
    assert len(result.challenge_executions) == 2
    assert all(item.classification == "survived" for item in result.challenge_executions)
