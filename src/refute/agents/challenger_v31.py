from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .investigator import Investigation
from .reproducer import _extract_json_object, validate_generated_test

SYSTEM_PROMPT = """You are the Challenger in a software patch verification system.
Your job is to propose ONE nearby falsification test for a patch whose public reported trigger now passes.

Return exactly one JSON object:
{
  "kind": "remaining_requirement | regression_guard",
  "grounding_quote": "an exact short quote copied from the issue report that justifies the asserted behavior",
  "rationale": "why this nearby case could falsify the patch",
  "test_code": "complete pytest-compatible Python source"
}

Definitions:
- remaining_requirement: another behavior explicitly required by the issue may still be broken on both original and patch.
- regression_guard: behavior that should remain valid may pass on the original but fail on the patch.

Constraints:
- grounding_quote MUST be copied verbatim from the issue report and must directly justify the assertion;
- do not test inputs or behavior outside the contract stated in the issue;
- do NOT merely repeat the already-repaired public trigger;
- prefer one high-value boundary, invariant-preservation case, small-limit case, or exception-specificity case;
- use only local project code and Python/pytest facilities;
- do not use network access, subprocesses, shell commands, file deletion, eval, exec, or dynamic imports;
- do not modify project files;
- do not reference expected verdicts, evaluator oracles, hidden tests, or benchmark internals;
- JSON must be syntactically valid and contain no surrounding commentary.
"""


class ChallengeGenerationErrorV31(ValueError):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True, slots=True)
class ChallengeCandidateV31:
    attempt: int
    kind: str
    grounding_quote: str
    rationale: str
    test_code: str
    raw_response: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def build_challenger_prompt_v31(
    case: VerificationCase,
    investigation: Investigation,
    *,
    attempt: int,
    feedback: str | None = None,
) -> str:
    diff = build_static_diff(case) or "(No source differences detected.)"
    parts = [
        f"ATTEMPT: {attempt}",
        f"ISSUE REPORT:\n{case.issue_text.strip()}",
        "INVESTIGATION:\n" + json.dumps(investigation.to_dict(), indent=2),
        f"PATCH DIFF:\n```diff\n{diff}\n```",
        "PUBLIC EXECUTION FACT: the reported public trigger changed from FAIL on the original to PASS on the patch.",
        "Propose one different nearby test. Copy a short exact grounding_quote from the issue report.",
    ]
    if feedback:
        parts.append(f"PRIOR CHALLENGE FEEDBACK:\n{feedback}")
    return "\n\n".join(parts) + "\n"


def generate_challenge_v31(
    case: VerificationCase,
    investigation: Investigation,
    llm: LLM,
    *,
    attempt: int,
    feedback: str | None = None,
) -> ChallengeCandidateV31:
    raw = llm.complete(
        SYSTEM_PROMPT,
        build_challenger_prompt_v31(case, investigation, attempt=attempt, feedback=feedback),
    )
    try:
        payload = _extract_json_object(raw)
        kind = payload.get("kind")
        grounding_quote = payload.get("grounding_quote")
        rationale = payload.get("rationale")
        test_code = payload.get("test_code")

        if kind not in {"remaining_requirement", "regression_guard"}:
            raise ValueError("challenger kind must be remaining_requirement or regression_guard")
        if not isinstance(grounding_quote, str) or not grounding_quote.strip():
            raise ValueError("challenger grounding_quote must be a non-empty string")
        if _normalize(grounding_quote) not in _normalize(case.issue_text):
            raise ValueError("challenger grounding_quote is not an exact issue-report quote")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("challenger rationale must be a non-empty string")
        if not isinstance(test_code, str) or not test_code.strip():
            raise ValueError("challenger test_code must be a non-empty string")
        validate_generated_test(test_code)

        return ChallengeCandidateV31(
            attempt=attempt,
            kind=kind,
            grounding_quote=grounding_quote.strip(),
            rationale=rationale.strip(),
            test_code=test_code.rstrip() + "\n",
            raw_response=raw,
        )
    except ValueError as exc:
        raise ChallengeGenerationErrorV31(str(exc), raw) from exc
