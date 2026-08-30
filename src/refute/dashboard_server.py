from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .case import CaseFormatError, load_case
from .github_pr import (
    GitHubPRIngestionError,
    fetch_github_pr_metadata,
    prepare_github_pr_case,
)
from .llm import LLMError, provider_from_env
from .real_repo_adversary import run_nearby_adversary
from .verify_v5 import verify_case_v5


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = REPO_ROOT / "benchmark_v2"
GITHUB_WORKSPACE_ROOT = REPO_ROOT / "artifacts" / "github-workspaces"


def _execution_payload(result) -> dict[str, object]:
    return {
        "passed": result.passed,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _case_payload(case_dir: Path) -> dict[str, object]:
    case = load_case(case_dir)
    title = case.issue_text.splitlines()[0].lstrip("# ").strip() if case.issue_text.strip() else case.case_id
    return {
        "case_id": case.case_id,
        "title": title,
        "issue_text": case.issue_text,
        "test_command": " ".join(case.test_command),
    }


def _verification_payload(result, case, *, source: dict[str, object] | None = None) -> dict[str, object]:
    probes = []
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
        "issue_text": case.issue_text,
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


def _github_metadata_payload(metadata) -> dict[str, object]:
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


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "refute-dashboard/0.4"

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "iteration": "5", "github_pr_mode": True})
            return
        if path == "/api/cases":
            try:
                roots = sorted(DEFAULT_BENCHMARK_ROOT.glob("case_*"))
                self._send_json(HTTPStatus.OK, {"cases": [_case_payload(root) for root in roots]})
            except (CaseFormatError, OSError, ValueError) as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path.startswith("/api/cases/"):
            case_id = path.rsplit("/", 1)[-1]
            case_dir = DEFAULT_BENCHMARK_ROOT / case_id
            if not case_dir.is_dir():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"unknown case: {case_id}"})
                return
            try:
                self._send_json(HTTPStatus.OK, _case_payload(case_dir))
            except (CaseFormatError, OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/github/inspect":
            self._inspect_github_pr()
            return
        if path == "/api/github/verify":
            self._verify_github_pr()
            return
        if path.startswith("/api/verify/"):
            self._verify_benchmark(path.rsplit("/", 1)[-1])
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def _inspect_github_pr(self) -> None:
        try:
            request = self._read_json()
            url = str(request.get("url", "")).strip()
            metadata = fetch_github_pr_metadata(url)
            self._send_json(HTTPStatus.OK, _github_metadata_payload(metadata))
        except (GitHubPRIngestionError, OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def _verify_github_pr(self) -> None:
        try:
            request = self._read_json()
            if request.get("confirm_execution") is not True:
                raise ValueError("explicit local execution confirmation is required")
            url = str(request.get("url", "")).strip()
            provider = str(request.get("provider", "ollama"))
            model = str(request.get("model", "qwen3:0.6b"))
            llm_timeout = float(request.get("llm_timeout", 30.0))
            execution_timeout = float(request.get("execution_timeout", 30.0))

            metadata = fetch_github_pr_metadata(url)
            case = prepare_github_pr_case(metadata, GITHUB_WORKSPACE_ROOT)
            llm = provider_from_env(provider, model, timeout_seconds=llm_timeout)
            result = verify_case_v5(
                case,
                llm,
                artifacts_root=REPO_ROOT / "artifacts",
                timeout_seconds=execution_timeout,
            )
            source = _github_metadata_payload(metadata)
            source["mode"] = "github_pr"
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
                        "The reported trigger is repaired, but an agent-prioritized existing nearby test passes on the base revision "
                        f"and fails on the patch: {first.candidate.nodeid}."
                    )
                    payload["challenge_counterexamples"] = int(payload["challenge_counterexamples"]) + 1

            self._send_json(HTTPStatus.OK, payload)
        except (GitHubPRIngestionError, CaseFormatError, LLMError, OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def _verify_benchmark(self, case_id: str) -> None:
        case_dir = DEFAULT_BENCHMARK_ROOT / case_id
        if not case_dir.is_dir():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"unknown case: {case_id}"})
            return
        try:
            request = self._read_json()
            provider = str(request.get("provider", "ollama"))
            model = str(request.get("model", "qwen3:0.6b"))
            llm_timeout = float(request.get("llm_timeout", 30.0))
            execution_timeout = float(request.get("execution_timeout", 20.0))
            case = load_case(case_dir)
            llm = provider_from_env(provider, model, timeout_seconds=llm_timeout)
            result = verify_case_v5(
                case,
                llm,
                artifacts_root=REPO_ROOT / "artifacts",
                timeout_seconds=execution_timeout,
            )
            self._send_json(HTTPStatus.OK, _verification_payload(result, case, source={"mode": "benchmark"}))
        except (CaseFormatError, LLMError, OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} - {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the local refute dashboard API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"refute dashboard API listening on http://{args.host}:{args.port}")
    print(f"benchmark root: {DEFAULT_BENCHMARK_ROOT}")
    print("real-repo mode: public GitHub PRs, Python + pytest, explicit local execution confirmation")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
