from __future__ import annotations

import difflib
import json
from pathlib import Path

from .llm import LLM
from .models import BaselineResult, Verdict, VerificationCase

SYSTEM_PROMPT = """You are reviewing a proposed software bug fix.

Your task is intentionally limited: perform a STATIC review only.
Do not claim that code was executed, tests were run, or the bug was reproduced.

Return exactly one JSON object with this schema:
{
  "verdict": "complete_fix | partial_fix | ineffective_fix | regression_introduced | inconclusive",
  "reason": "brief evidence-based explanation"
}

Use only the issue report and code diff supplied to you. If the available static evidence is insufficient, return inconclusive.
"""


def build_static_diff(case: VerificationCase) -> str:
    original_files = _python_files(case.original_path)
    patched_files = _python_files(case.patched_path)
    relative_paths = sorted(set(original_files) | set(patched_files))

    chunks: list[str] = []
    for relative in relative_paths:
        original_text = original_files.get(relative, "").splitlines(keepends=True)
        patched_text = patched_files.get(relative, "").splitlines(keepends=True)
        if original_text == patched_text:
            continue
        diff = difflib.unified_diff(
            original_text,
            patched_text,
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
        chunks.extend(diff)

    return "".join(chunks).strip()


def build_baseline_prompt(case: VerificationCase) -> str:
    diff = build_static_diff(case)
    if not diff:
        diff = "(No source differences detected.)"
    return (
        f"CASE ID: {case.case_id}\n\n"
        f"ISSUE REPORT:\n{case.issue_text.strip()}\n\n"
        f"PATCH DIFF:\n```diff\n{diff}\n```\n"
    )


def run_baseline(
    case: VerificationCase,
    llm: LLM,
    artifacts_root: str | Path = "artifacts",
) -> BaselineResult:
    prompt = build_baseline_prompt(case)
    raw_response = llm.complete(SYSTEM_PROMPT, prompt)
    verdict, reason = parse_baseline_response(raw_response)

    case_artifacts = Path(artifacts_root).resolve() / case.case_id / "baseline"
    case_artifacts.mkdir(parents=True, exist_ok=True)

    prompt_path = case_artifacts / "prompt.txt"
    response_path = case_artifacts / "response.txt"
    result_path = case_artifacts / "result.json"

    prompt_path.write_text(
        f"SYSTEM:\n{SYSTEM_PROMPT}\n\nUSER:\n{prompt}", encoding="utf-8"
    )
    response_path.write_text(raw_response, encoding="utf-8")
    result_path.write_text(
        json.dumps(
            {
                "case_id": case.case_id,
                "verdict": verdict.value,
                "reason": reason,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return BaselineResult(
        case_id=case.case_id,
        verdict=verdict,
        reason=reason,
        raw_response=raw_response,
        prompt_path=prompt_path,
        response_path=response_path,
        result_path=result_path,
    )


def parse_baseline_response(raw_response: str) -> tuple[Verdict, str]:
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            candidate = "\n".join(lines[1:-1])
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:].lstrip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("baseline model did not return valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("baseline model response must be a JSON object")

    try:
        verdict = Verdict(payload.get("verdict"))
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(v.value for v in Verdict)
        raise ValueError(f"baseline verdict must be one of: {allowed}") from exc

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("baseline reason must be a non-empty string")

    return verdict, reason.strip()


def _python_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = path.read_text(encoding="utf-8")
    return files
