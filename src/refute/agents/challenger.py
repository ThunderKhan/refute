from __future__ import annotations

import json
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .investigator import Investigation
from .reproducer import _extract_json_object, validate_generated_test

SYSTEM_PROMPT = """You are the Challenger in a software patch verification system.
Your job is to try to falsify a patch that appears to fix the reported bug.

Generate 1 to 3 focused pytest tests for nearby behavior that is implied by the issue report or by a plausible regression risk in the patch diff. Prefer boundaries, neighboring inputs, preserved invariants, and exception behavior.

Return exactly one JSON object:
{
  "candidates": [
    {
      "rationale": "why this nearby case could falsify the patch",
      "test_code": "complete pytest-compatible Python source"
    }
  ]
}

Constraints:
- do NOT merely repeat the public reported-trigger test;
- every expected behavior asserted by a test must be grounded in the issue report or a clear invariant exposed by the patch;
- use only local project code and Python/pytest facilities;
- do not use network access, subprocesses, shell commands, file deletion, eval, exec, or dynamic imports;
- do not modify project files;
- do not reference expected verdicts, evaluator oracles, hidden tests, or benchmark internals;
- produce at most 3 candidates;
- JSON must be syntactically valid and contain no surrounding commentary.
"""


class ChallengeGenerationError(ValueError):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True, slots=True)
class ChallengeCandidate:
    index: int
    rationale: str
    test_code: str


@dataclass(frozen=True, slots=True)
class ChallengePlan:
    candidates: tuple[ChallengeCandidate, ...]
    raw_response: str


def build_challenger_prompt(case: VerificationCase, investigation: Investigation) -> str:
    diff = build_static_diff(case) or "(No source differences detected.)"
    return (
        f"CASE ID: {case.case_id}\n\n"
        f"ISSUE REPORT:\n{case.issue_text.strip()}\n\n"
        "INVESTIGATION:\n"
        + json.dumps(investigation.to_dict(), indent=2)
        + f"\n\nPATCH DIFF:\n```diff\n{diff}\n```\n"
        + "\nThe public reported-trigger test has already changed from FAIL on the original to PASS on the patch. "
        "Challenge the patch with nearby behavior rather than repeating that trigger.\n"
    )


def generate_challenges(
    case: VerificationCase,
    investigation: Investigation,
    llm: LLM,
) -> ChallengePlan:
    raw = llm.complete(SYSTEM_PROMPT, build_challenger_prompt(case, investigation))
    try:
        return parse_challenges(raw)
    except ValueError as exc:
        raise ChallengeGenerationError(str(exc), raw) from exc


def parse_challenges(raw: str) -> ChallengePlan:
    payload = _extract_json_object(raw)
    candidates_raw = payload.get("candidates")
    if not isinstance(candidates_raw, list) or not 1 <= len(candidates_raw) <= 3:
        raise ValueError("challenger candidates must contain between 1 and 3 items")

    candidates: list[ChallengeCandidate] = []
    for index, item in enumerate(candidates_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError("challenger candidate must be a JSON object")
        rationale = item.get("rationale")
        test_code = item.get("test_code")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("challenger rationale must be a non-empty string")
        if not isinstance(test_code, str) or not test_code.strip():
            raise ValueError("challenger test_code must be a non-empty string")
        validate_generated_test(test_code)
        candidates.append(
            ChallengeCandidate(
                index=index,
                rationale=rationale.strip(),
                test_code=test_code.rstrip() + "\n",
            )
        )

    return ChallengePlan(candidates=tuple(candidates), raw_response=raw)
