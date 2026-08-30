from __future__ import annotations

import json
from dataclasses import dataclass

from ..llm import LLM
from .reproducer import _extract_json_object

SYSTEM_PROMPT = """You are a strict evidence critic in a software patch verification system.
You are given ONE public issue contract span and ONE generated pytest challenge.
Decide only whether the test's asserted behavior is directly justified by that contract span.
Do not judge whether the patch is good. Do not infer unstated requirements.

Return exactly one JSON object:
{
  "supported": true | false,
  "reason": "brief explanation"
}

Rules:
- supported=true only when the assertion follows directly from the supplied contract text;
- reject tests that use inputs outside an explicit range or invent outputs/exceptions not stated or clearly implied;
- reject tests that merely assert an arbitrary implementation preference;
- be conservative when ambiguous.
"""


@dataclass(frozen=True, slots=True)
class ChallengeCritiqueV33:
    supported: bool
    reason: str
    raw_response: str


def critique_challenge_v33(
    llm: LLM,
    *,
    contract_text: str,
    test_code: str,
) -> ChallengeCritiqueV33:
    prompt = (
        f"CONTRACT SPAN:\n{contract_text.strip()}\n\n"
        f"GENERATED PYTEST:\n```python\n{test_code.rstrip()}\n```\n"
    )
    raw = llm.complete(SYSTEM_PROMPT, prompt)
    payload = _extract_json_object(raw)
    supported = payload.get("supported")
    reason = payload.get("reason")
    if not isinstance(supported, bool):
        raise ValueError("challenge critic supported must be boolean")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("challenge critic reason must be a non-empty string")
    return ChallengeCritiqueV33(supported=supported, reason=reason.strip(), raw_response=raw)
