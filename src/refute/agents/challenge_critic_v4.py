from __future__ import annotations

import json
from dataclasses import dataclass

from ..llm import LLM
from .challenger_v4 import ChallengeIntentV4
from .reproducer import _extract_json_object


SYSTEM_PROMPT = """You are an evidence critic in a software patch verification system.
You are given ONE public issue contract span and ONE STRUCTURED test intent. Decide only whether the intended assertion is justified by the supplied contract.

Return exactly one JSON object:
{
  "supported": true | false,
  "reason": "brief explanation"
}

Rules:
- supported=true only when the input and expectation follow directly from the supplied contract text;
- reject out-of-contract inputs and invented output/exception behavior;
- for ranges, boundaries explicitly included by the contract are valid tests;
- for preservation requirements, a representative preserved value is valid;
- for exception requirements, the named exception must be directly stated or unambiguously required by the contract;
- judge the intent, not the implementation or observed result;
- be conservative when ambiguous.
"""


@dataclass(frozen=True, slots=True)
class IntentCritiqueV4:
    supported: bool
    reason: str
    raw_response: str


def critique_intent_v4(llm: LLM, intent: ChallengeIntentV4) -> IntentCritiqueV4:
    expectation: dict[str, object] = {"type": intent.expectation_type}
    if intent.expectation_type == "equals":
        expectation["value"] = intent.expected_value
    elif intent.expectation_type == "raises":
        expectation["exception"] = intent.expected_exception
    else:
        expectation["arg_index"] = intent.arg_index

    prompt = (
        f"CONTRACT SPAN:\n{intent.contract_text.strip()}\n\n"
        "STRUCTURED INTENT:\n"
        + json.dumps(
            {
                "kind": intent.kind,
                "target": intent.target,
                "args": list(intent.args),
                "expectation": expectation,
                "rationale": intent.rationale,
            },
            indent=2,
        )
        + "\n"
    )
    raw = llm.complete(SYSTEM_PROMPT, prompt)
    payload = _extract_json_object(raw)
    supported = payload.get("supported")
    reason = payload.get("reason")
    if not isinstance(supported, bool):
        raise ValueError("intent critic supported must be boolean")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("intent critic reason must be a non-empty string")
    return IntentCritiqueV4(supported=supported, reason=reason.strip(), raw_response=raw)
