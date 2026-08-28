from __future__ import annotations

import json
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase

SYSTEM_PROMPT = """You are the Investigator in a software patch verification system.
Your job is to turn an issue report and patch diff into a precise verification hypothesis.
Do not claim that code was executed or that the bug was reproduced.
Return exactly one JSON object with this schema:
{
  "expected_behavior": "...",
  "reported_failure": "...",
  "trigger_conditions": ["..."],
  "likely_files": ["..."],
  "reproduction_strategy": "...",
  "risk_areas": ["..."]
}
Be concrete and conservative. If the issue is ambiguous, state the ambiguity in the relevant fields.
"""


@dataclass(frozen=True, slots=True)
class Investigation:
    expected_behavior: str
    reported_failure: str
    trigger_conditions: tuple[str, ...]
    likely_files: tuple[str, ...]
    reproduction_strategy: str
    risk_areas: tuple[str, ...]
    raw_response: str

    def to_dict(self) -> dict:
        return {
            "expected_behavior": self.expected_behavior,
            "reported_failure": self.reported_failure,
            "trigger_conditions": list(self.trigger_conditions),
            "likely_files": list(self.likely_files),
            "reproduction_strategy": self.reproduction_strategy,
            "risk_areas": list(self.risk_areas),
        }


def build_investigator_prompt(case: VerificationCase) -> str:
    diff = build_static_diff(case) or "(No source differences detected.)"
    return (
        f"CASE ID: {case.case_id}\n\n"
        f"ISSUE REPORT:\n{case.issue_text.strip()}\n\n"
        f"PATCH DIFF:\n```diff\n{diff}\n```\n"
    )


def investigate(case: VerificationCase, llm: LLM) -> Investigation:
    raw = llm.complete(SYSTEM_PROMPT, build_investigator_prompt(case))
    return parse_investigation(raw)


def parse_investigation(raw: str) -> Investigation:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            candidate = "\n".join(lines[1:-1])
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:].lstrip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("investigator did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("investigator response must be a JSON object")

    def text(name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"investigator field {name} must be a non-empty string")
        return value.strip()

    def strings(name: str) -> tuple[str, ...]:
        value = payload.get(name)
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"investigator field {name} must be an array of non-empty strings")
        return tuple(item.strip() for item in value)

    return Investigation(
        expected_behavior=text("expected_behavior"),
        reported_failure=text("reported_failure"),
        trigger_conditions=strings("trigger_conditions"),
        likely_files=strings("likely_files"),
        reproduction_strategy=text("reproduction_strategy"),
        risk_areas=strings("risk_areas"),
        raw_response=raw,
    )
