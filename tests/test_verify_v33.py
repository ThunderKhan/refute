from __future__ import annotations

import json
from pathlib import Path

from refute.agents.challenge_critic_v33 import critique_challenge_v33
from refute.case import load_case
from refute.models import Verdict
from refute.verify_v33 import verify_case_v33


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(self, system: str, user: str) -> str:
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _make_case(tmp_path: Path, *, case_id: str, issue: str, original_app: str, patched_app: str, public_test: str):
    root = tmp_path / case_id
    for version, app in (("original", original_app), ("patched", patched_app)):
        version_dir = root / version
        version_dir.mkdir(parents=True)
        (version_dir / "app.py").write_text(app, encoding="utf-8")
        (version_dir / "test_app.py").write_text(public_test, encoding="utf-8")
    (root / "issue.md").write_text(issue, encoding="utf-8")
    (root / "case.json").write_text(
        json.dumps({"case_id": case_id, "test_command": ["python", "-m", "pytest", "-q"]}),
        encoding="utf-8",
    )
    return load_case(root)


def test_critic_parses_supported_boolean():
    llm = SequencedLLM([json.dumps({"supported": True, "reason": "the assertion is directly stated"})])
    critique = critique_challenge_v33(
        llm,
        contract_text="Values from 0 through 100 inclusive are valid.",
        test_code="def test_x():\n    assert True\n",
    )
    assert critique.supported is True


def test_v33_accepts_critic_supported_remaining_requirement(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="partial",
        issue="Values from 0 through 100 inclusive are valid. The lower boundary is currently rejected.",
        original_app=(
            "def normalize_percentage(value):\n"
            "    if value <= 0 or value >= 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        patched_app=(
            "def normalize_percentage(value):\n"
            "    if value < 0 or value >= 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        public_test="from app import normalize_percentage\n\ndef test_zero():\n    assert normalize_percentage(0) == 0\n",
    )
    challenge = json.dumps({
        "kind": "remaining_requirement",
        "contract_id": "c1",
        "rationale": "upper inclusive boundary",
        "test_code": "from app import normalize_percentage\n\ndef test_upper():\n    assert normalize_percentage(100) == 100\n",
    })
    critic = json.dumps({"supported": True, "reason": "100 is explicitly inside the inclusive range"})
    result = verify_case_v33(
        case,
        SequencedLLM([challenge, critic]),
        artifacts_root=tmp_path / "artifacts",
        timeout_seconds=10,
    )
    assert result.verdict is Verdict.PARTIAL_FIX
    assert result.critic_called is True
    assert result.challenge_executions[0].classification == "remaining_requirement_counterexample"


def test_v33_rejects_unsupported_failure_and_can_recover_with_surviving_retry(tmp_path: Path):
    case = _make_case(
        tmp_path,
        case_id="complete",
        issue="Values from 0 through 100 inclusive are valid. Zero is currently rejected.",
        original_app=(
            "def clamp(value):\n"
            "    if value <= 0 or value > 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        patched_app=(
            "def clamp(value):\n"
            "    if value < 0 or value > 100:\n"
            "        raise ValueError\n"
            "    return value\n"
        ),
        public_test="from app import clamp\n\ndef test_zero():\n    assert clamp(0) == 0\n",
    )
    bad = json.dumps({
        "kind": "remaining_requirement",
        "contract_id": "c1",
        "rationale": "invent an out-of-range requirement",
        "test_code": "from app import clamp\n\ndef test_bad():\n    assert clamp(-1) == -1\n",
    })
    critic_rejects = json.dumps({"supported": False, "reason": "-1 is outside the stated valid range"})
    good = json.dumps({
        "kind": "remaining_requirement",
        "contract_id": "c1",
        "rationale": "upper boundary remains in-range",
        "test_code": "from app import clamp\n\ndef test_upper():\n    assert clamp(100) == 100\n",
    })
    result = verify_case_v33(
        case,
        SequencedLLM([bad, critic_rejects, good]),
        artifacts_root=tmp_path / "artifacts",
        timeout_seconds=10,
    )
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.challenge_executions[0].classification == "unsupported_counterexample"
    assert result.challenge_executions[1].classification == "survived"
