from __future__ import annotations

import re
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .probe_compiler_v5 import ContractProbeV5


SYSTEM_PROMPT = """You are a probe-selection planner in a software patch verification system.
You are given a small deterministic set of public-contract-grounded probe IDs.
Choose the probes most likely to falsify the patch while staying within the public issue contract.

Return only a comma-separated list of probe IDs, for example:
p2,p1

Rules:
- choose only supplied probe IDs;
- choose at most the requested budget;
- prefer boundaries, preserved invariants, exception specificity, and behavior closest to the patch diff;
- do not add explanations, JSON, code, hidden tests, or verdicts.
"""


@dataclass(frozen=True, slots=True)
class ProbePlanV5:
    selected_ids: tuple[str, ...]
    raw_response: str
    used_fallback: bool


def plan_probes_v5(
    case: VerificationCase,
    probes: tuple[ContractProbeV5, ...],
    llm: LLM,
    *,
    budget: int,
) -> ProbePlanV5:
    if budget < 1:
        raise ValueError("probe budget must be at least 1")
    if not probes:
        return ProbePlanV5((), "", False)

    allowed = {probe.probe_id: probe for probe in probes}
    prompt = [
        f"ISSUE REPORT:\n{case.issue_text.strip()}",
        f"PATCH DIFF:\n{build_static_diff(case) or '(no source differences detected)'}",
        f"PROBE BUDGET: {min(budget, len(probes))}",
        "AVAILABLE PROBES:",
    ]
    for probe in probes:
        prompt.append(
            f"{probe.probe_id}: [{probe.kind}] {probe.description} | contract: {probe.contract_text}"
        )
    raw = llm.complete(SYSTEM_PROMPT, "\n\n".join(prompt) + "\n")

    selected: list[str] = []
    for match in re.findall(r"\bp\d+\b", raw.casefold()):
        if match in allowed and match not in selected:
            selected.append(match)
        if len(selected) >= budget:
            break

    used_fallback = False
    if not selected:
        used_fallback = True
        selected = [probe.probe_id for probe in probes[:budget]]

    return ProbePlanV5(tuple(selected), raw, used_fallback)
