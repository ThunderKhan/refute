from __future__ import annotations

import json
import re
from pathlib import Path

from mcp.server import MCPServer

from refute.github_pr import fetch_github_pr_metadata, prepare_github_pr_case
from refute.llm import provider_from_env
from refute.real_repo_adversary import run_nearby_adversary
from refute.verify_v5 import verify_case_v5


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"
GITHUB_WORKSPACE_ROOT = ARTIFACTS_ROOT / "github-workspaces"

mcp = MCPServer("refute")


def _execution_payload(result) -> dict[str, object]:
    return {
        "passed": result.passed,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _metadata_payload(metadata) -> dict[str, object]:
    return {
        "url": metadata.url,
        "owner": metadata.owner,
        "repo": metadata.repo,
        "number": metadata.number,
        "title": metadata.title,
        "body": metadata.body,
        "base_sha": metadata.base_sha,
        "head_sha": metadata.head_sha,
        "changed_files": metadata.changed_files,
        "additions": metadata.additions,
        "deletions": metadata.deletions,
        "linked_issue_number": metadata.linked_issue_number,
        "linked_issue_title": metadata.linked_issue_title,
        "issue_text": metadata.issue_text,
    }


def _verification_payload(result, case, *, source: dict[str, object]) -> dict[str, object]:
    probes: list[dict[str, object]] = []
    for execution in result.challenge_executions:
        probes.append(
            {
                "probe_id": execution.probe.probe_id,
                "description": execution.probe.description,
                "kind": execution.probe.kind,
                "contract_id": execution.probe.contract_id,
                "contract_text": execution.probe.contract_text,
                "classification": execution.classification,
                "original": _execution_payload(execution.original),
                "patched": _execution_payload(execution.patched),
            }
        )

    return {
        "run_id": result.run_id,
        "case_id": result.case_id,
        "verdict": result.verdict.value,
        "reason": result.reason,
        "test_delta": result.test_delta.classification,
        "original": _execution_payload(result.original),
        "patched": _execution_payload(result.patched),
        "planner_called": result.planner_called,
        "planner_fallback": result.planner_fallback,
        "challenger_called": result.challenger_called,
        "challenge_generation_failures": list(result.challenge_generation_failures),
        "challenge_counterexamples": sum(item.is_counterexample for item in result.challenge_executions),
        "probes": probes,
        "evidence_path": str(result.run_root.resolve()),
        "source": source,
        "nearby_adversary": None,
    }


def _nearby_payload(result) -> dict[str, object]:
    return {
        "candidate_count": len(result.candidates),
        "selected_ids": list(result.selected_ids),
        "used_fallback": result.used_fallback,
        "collection_error": result.collection_error,
        "executions": [
            {
                "candidate_id": item.candidate.candidate_id,
                "nodeid": item.candidate.nodeid,
                "classification": item.classification,
                "original": _execution_payload(item.original),
                "patched": _execution_payload(item.patched),
            }
            for item in result.executions
        ],
    }


@mcp.tool()
def inspect_pr(url: str) -> dict[str, object]:
    """Inspect a public GitHub pull request without executing repository code.

    Returns public PR metadata, base/head revisions, change counts, linked issue
    information when available, and the public issue/PR contract used by refute.
    """
    metadata = fetch_github_pr_metadata(url)
    return _metadata_payload(metadata)


@mcp.tool()
def verify_pr(
    url: str,
    confirm_execution: bool = False,
    provider: str = "ollama",
    model: str = "qwen3:0.6b",
    llm_timeout: float = 30.0,
    execution_timeout: float = 30.0,
) -> dict[str, object]:
    """Verify a public Python/pytest GitHub PR and return structured evidence.

    This tool clones the target revisions, creates an isolated environment,
    installs the repository's declared Python/test dependencies, and executes
    third-party tests locally. Set confirm_execution=true only after the human
    has explicitly approved that local execution.
    """
    if confirm_execution is not True:
        raise ValueError(
            "explicit local execution approval is required; call inspect_pr first, "
            "tell the user that dependencies/tests will run locally, then retry with confirm_execution=true"
        )
    if llm_timeout <= 0 or execution_timeout <= 0:
        raise ValueError("timeouts must be greater than zero")

    metadata = fetch_github_pr_metadata(url)
    case = prepare_github_pr_case(metadata, GITHUB_WORKSPACE_ROOT)
    llm = provider_from_env(provider, model, timeout_seconds=llm_timeout)
    result = verify_case_v5(
        case,
        llm,
        artifacts_root=ARTIFACTS_ROOT,
        timeout_seconds=execution_timeout,
    )

    source = _metadata_payload(metadata)
    source["mode"] = "github_pr_mcp"
    source["workspace"] = str(case.root.resolve())
    source["test_command"] = " ".join(case.test_command)
    source["reproduction_targets"] = list(case.test_command[2:])
    source["reproduction_mode"] = (
        "patch_changed_tests" if len(case.test_command) > 2 else "full_suite_fallback"
    )

    payload = _verification_payload(result, case, source=source)

    if result.test_delta.classification == "suite_repaired" and result.verdict.value == "inconclusive":
        nearby = run_nearby_adversary(
            case,
            llm,
            budget=3,
            timeout_seconds=execution_timeout,
        )
        nearby_payload = _nearby_payload(nearby)
        payload["nearby_adversary"] = nearby_payload
        (result.run_root / "nearby_adversary.json").write_text(
            json.dumps(nearby_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        regressions = [item for item in nearby.executions if item.is_regression]
        if regressions:
            first = regressions[0]
            payload["verdict"] = "regression_introduced"
            payload["reason"] = (
                "The reported trigger is repaired, but an existing nearby test passes on the base revision "
                f"and fails on the patch: {first.candidate.nodeid}."
            )
            payload["challenge_counterexamples"] = int(payload["challenge_counterexamples"]) + 1
        elif nearby.executions:
            survived = sum(item.classification == "survived" for item in nearby.executions)
            payload["reason"] = (
                f"The reported trigger is repaired and the bounded nearby-test adversary found no regression across "
                f"{survived} surviving existing tests. No independent contract-derived counterexample or sufficient "
                "completeness evidence was available, so the verdict remains inconclusive."
            )

    (result.run_root / "mcp_result.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


@mcp.tool()
def get_run(run_id: str) -> dict[str, object]:
    """Read a previously recorded refute run by run ID without executing code."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise ValueError("invalid run_id")
    run_root = (ARTIFACTS_ROOT / run_id).resolve()
    if run_root.parent != ARTIFACTS_ROOT.resolve():
        raise ValueError("invalid run_id")

    preferred = run_root / "mcp_result.json"
    fallback = run_root / "result.json"
    path = preferred if preferred.is_file() else fallback
    if not path.is_file():
        raise ValueError(f"unknown run_id: {run_id}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("recorded run is not a JSON object")

    nearby_path = run_root / "nearby_adversary.json"
    if "nearby_adversary" not in payload and nearby_path.is_file():
        nearby = json.loads(nearby_path.read_text(encoding="utf-8"))
        if isinstance(nearby, dict):
            payload["nearby_adversary"] = nearby
    return payload


def main() -> int:
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
