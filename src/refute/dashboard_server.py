from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .case import CaseFormatError, load_case
from .llm import LLMError, provider_from_env
from .verify_v5 import verify_case_v5


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = REPO_ROOT / "benchmark_v2"


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
        "test_command": case.test_command,
    }


def _verification_payload(result, case) -> dict[str, object]:
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
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "refute-dashboard/0.1"

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

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "iteration": "5"})
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
        if not path.startswith("/api/verify/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        case_id = path.rsplit("/", 1)[-1]
        case_dir = DEFAULT_BENCHMARK_ROOT / case_id
        if not case_dir.is_dir():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"unknown case: {case_id}"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request body must be a JSON object")
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
            self._send_json(HTTPStatus.OK, _verification_payload(result, case))
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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
