from __future__ import annotations

import ast
import json
from dataclasses import dataclass

from ..baseline import build_static_diff
from ..llm import LLM
from ..models import VerificationCase
from .investigator import Investigation

SYSTEM_PROMPT = """You are the Reproducer in a software patch verification system.
Your job is to generate ONE focused pytest test that should fail on the buggy original implementation if the reported issue is reproducible, and pass when the reported bug is correctly fixed.

Return exactly one JSON object:
{
  "rationale": "brief explanation of what the test targets",
  "test_code": "complete pytest-compatible Python source"
}

Constraints:
- generate a focused test, not a broad regression suite;
- use only local project code and Python/pytest facilities;
- do not use network access, subprocesses, file deletion, shell commands, eval, exec, or dynamic imports;
- do not modify project files;
- do not encode or reference the benchmark's expected verdict;
- if prior execution feedback is supplied, revise the test to better reproduce the reported issue.
"""


@dataclass(frozen=True, slots=True)
class ReproductionCandidate:
    attempt: int
    rationale: str
    test_code: str
    raw_response: str


def build_reproducer_prompt(
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
    ]
    if feedback:
        parts.append(f"PRIOR EXECUTION FEEDBACK:\n{feedback}")
    return "\n\n".join(parts) + "\n"


def generate_reproduction(
    case: VerificationCase,
    investigation: Investigation,
    llm: LLM,
    *,
    attempt: int,
    feedback: str | None = None,
) -> ReproductionCandidate:
    raw = llm.complete(
        SYSTEM_PROMPT,
        build_reproducer_prompt(case, investigation, attempt=attempt, feedback=feedback),
    )
    return parse_reproduction(raw, attempt=attempt)


def parse_reproduction(raw: str, *, attempt: int) -> ReproductionCandidate:
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
        raise ValueError("reproducer did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("reproducer response must be a JSON object")
    rationale = payload.get("rationale")
    test_code = payload.get("test_code")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("reproducer rationale must be a non-empty string")
    if not isinstance(test_code, str) or not test_code.strip():
        raise ValueError("reproducer test_code must be a non-empty string")
    validate_generated_test(test_code)
    return ReproductionCandidate(
        attempt=attempt,
        rationale=rationale.strip(),
        test_code=test_code.rstrip() + "\n",
        raw_response=raw,
    )


def validate_generated_test(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"generated reproduction is invalid Python: {exc}") from exc

    blocked_modules = {"os", "subprocess", "socket", "shutil", "ctypes", "multiprocessing"}
    blocked_calls = {"eval", "exec", "open", "compile", "__import__", "input"}
    blocked_attrs = {"system", "popen", "remove", "unlink", "rmtree", "rmdir"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in blocked_modules:
                    raise ValueError(f"generated reproduction imports blocked module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module in blocked_modules:
                raise ValueError(f"generated reproduction imports blocked module: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                raise ValueError(f"generated reproduction uses blocked call: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in blocked_attrs:
                raise ValueError(f"generated reproduction uses blocked call: {node.func.attr}")
