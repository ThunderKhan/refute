from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .executor import run_command
from .llm import LLM, LLMError
from .models import ExecutionResult, VerificationCase


SYSTEM_PROMPT = """You are an adversarial test-selection planner for a software patch verifier.
The reported trigger has already been reproduced on the base revision and repaired by the patch.
Choose a small set of EXISTING nearby pytest tests that are most likely to expose a regression or an incomplete edge of the patch.

Return only comma-separated candidate IDs, for example:
t3,t1

Rules:
- choose only supplied IDs;
- choose at most the requested budget;
- prefer tests semantically adjacent to the changed behavior, error handling, boundaries, preserved invariants, and sibling code paths;
- do not write code, assertions, shell commands, verdicts, or explanations;
- do not assume hidden requirements.
"""


@dataclass(frozen=True, slots=True)
class NearbyTestCandidate:
    candidate_id: str
    nodeid: str


@dataclass(frozen=True, slots=True)
class NearbyTestExecution:
    candidate: NearbyTestCandidate
    original: ExecutionResult
    patched: ExecutionResult
    classification: str

    @property
    def is_regression(self) -> bool:
        return self.classification == "regression_counterexample"


@dataclass(frozen=True, slots=True)
class NearbyAdversaryResult:
    candidates: tuple[NearbyTestCandidate, ...]
    selected_ids: tuple[str, ...]
    raw_response: str
    used_fallback: bool
    executions: tuple[NearbyTestExecution, ...]
    collection_error: str | None = None


def _load_context(case: VerificationCase) -> dict:
    path = case.root / "github_context.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_nodeids(stdout: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if "::" not in line or line.startswith("="):
            continue
        if line not in values:
            values.append(line)
    return tuple(values)


def _test_name(nodeid: str) -> str:
    leaf = nodeid.rsplit("::", 1)[-1]
    return leaf.split("[", 1)[0]


def discover_nearby_tests(case: VerificationCase, *, timeout_seconds: float = 30.0, limit: int = 40) -> tuple[tuple[NearbyTestCandidate, ...], str | None]:
    if limit < 1:
        raise ValueError("candidate limit must be positive")
    context = _load_context(case)
    added = {str(value) for value in context.get("added_test_names", []) if isinstance(value, str)}
    command = tuple(case.test_command) + ("--collect-only",)
    collected = run_command(command, case.patched_path, timeout_seconds)
    if collected.timed_out or collected.exit_code not in {0, 5}:
        detail = (collected.stderr or collected.stdout).strip()
        return (), f"pytest collection failed: {detail[-500:]}"

    nodeids = [nodeid for nodeid in _parse_nodeids(collected.stdout) if _test_name(nodeid) not in added]
    nodeids = nodeids[:limit]
    candidates = tuple(NearbyTestCandidate(f"t{index + 1}", nodeid) for index, nodeid in enumerate(nodeids))
    return candidates, None


def _build_prompt(case: VerificationCase, candidates: tuple[NearbyTestCandidate, ...], budget: int) -> str:
    context = _load_context(case)
    diff = str(context.get("diff", ""))[:12000]
    changed_tests = context.get("changed_tests", [])
    parts = [
        f"ISSUE / PR:\n{case.issue_text.strip()}",
        f"CHANGED TEST FILES:\n{', '.join(str(x) for x in changed_tests) or '(none)'}",
        f"PATCH DIFF:\n{diff or '(diff unavailable)'}",
        f"BUDGET: {min(budget, len(candidates))}",
        "EXISTING NEARBY TEST CANDIDATES:",
    ]
    parts.extend(f"{candidate.candidate_id}: {candidate.nodeid}" for candidate in candidates)
    return "\n\n".join(parts) + "\n"


def run_nearby_adversary(case: VerificationCase, llm: LLM, *, budget: int = 3, timeout_seconds: float = 30.0) -> NearbyAdversaryResult:
    if budget < 1:
        raise ValueError("adversary budget must be positive")
    candidates, collection_error = discover_nearby_tests(case, timeout_seconds=timeout_seconds)
    if not candidates:
        return NearbyAdversaryResult((), (), "", False, (), collection_error)

    allowed = {candidate.candidate_id: candidate for candidate in candidates}
    raw = ""
    used_fallback = False
    try:
        raw = llm.complete(SYSTEM_PROMPT, _build_prompt(case, candidates, budget))
        selected: list[str] = []
        for match in re.findall(r"\bt\d+\b", raw.casefold()):
            if match in allowed and match not in selected:
                selected.append(match)
            if len(selected) >= budget:
                break
    except LLMError:
        selected = []

    if not selected:
        used_fallback = True
        selected = [candidate.candidate_id for candidate in candidates[:budget]]

    executions: list[NearbyTestExecution] = []
    runner_prefix = tuple(case.test_command[:2])
    for candidate_id in selected:
        candidate = allowed[candidate_id]
        original = run_command(runner_prefix + (candidate.nodeid,), case.original_path, timeout_seconds)
        patched = run_command(runner_prefix + (candidate.nodeid,), case.patched_path, timeout_seconds)
        if original.timed_out or patched.timed_out or original.exit_code not in {0, 1} or patched.exit_code not in {0, 1}:
            classification = "invalid_execution"
        elif original.passed and not patched.passed:
            classification = "regression_counterexample"
        elif not original.passed and patched.passed:
            classification = "repaired_neighbor"
        elif original.passed and patched.passed:
            classification = "survived"
        else:
            classification = "non_decisive"
        executions.append(NearbyTestExecution(candidate, original, patched, classification))
        if classification == "regression_counterexample":
            break

    return NearbyAdversaryResult(candidates, tuple(selected), raw, used_fallback, tuple(executions), collection_error)
