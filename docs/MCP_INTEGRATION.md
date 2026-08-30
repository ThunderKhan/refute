# refute MCP integration

`refute` exposes a local Model Context Protocol (MCP) server so coding agents can inspect and verify pull requests without going through the dashboard.

The server uses MCP over **stdio**. The host starts `refute-mcp` (or `python -m refute.mcp_server`) as a child process and receives structured tool results.

## Proven tool flow

The end-to-end flow has been exercised locally through MCP Inspector against a public GitHub PR:

```text
inspect_pr
   ↓
explicit human approval
   ↓
verify_pr → job_id
   ↓
get_verify_job(job_id) until complete
   ↓
get_run(run_id)
```

Long verification is asynchronous so an MCP host does not need to keep one tool request open for several minutes.

## Tools

### `inspect_pr`

Read-only. Fetches public GitHub PR metadata and the public PR/issue contract. It does **not** clone the repository, install dependencies, or execute code.

Input:

```json
{
  "url": "https://github.com/owner/repo/pull/123"
}
```

### `verify_pr`

Starts the real GitHub verification workflow.

This operation can clone third-party code, create an isolated Python environment, install the target repository's declared dependencies, and execute pytest tests locally. For that reason `confirm_execution` defaults to `false` and the tool refuses to start until the human explicitly approves local execution.

Input example:

```json
{
  "url": "https://github.com/owner/repo/pull/123",
  "confirm_execution": true,
  "provider": "ollama",
  "model": "qwen3:0.6b"
}
```

The call returns immediately with a job object:

```json
{
  "job_id": "verify-...",
  "status": "queued",
  "stage": "queued",
  "message": "Verification started. Poll get_verify_job with this job_id until complete."
}
```

### `get_verify_job`

Read-only polling for a `verify_pr` job. It does not start new execution.

Typical in-progress response:

```json
{
  "job_id": "verify-...",
  "status": "running",
  "stage": "preparing_workspace",
  "detail": "Cloning revisions and provisioning an isolated target environment",
  "result": null,
  "error": null,
  "run_id": null
}
```

When `status` becomes `complete`, `result` contains the structured verdict/evidence payload and `run_id` identifies the persisted evidence directory.

### `get_run`

Read-only. Reloads a previously recorded run from `artifacts/runs/<run_id>/` without executing repository code again.

The returned object can include the verdict, reason, base/patch execution evidence, deterministic probes, nearby-test adversary evidence, counterexample count, source metadata, and evidence path.

## Install

For development, the existing dev extra installs the MCP SDK:

```powershell
python -m pip install -e ".[dev]"
```

For an integration-only install:

```powershell
python -m pip install -e ".[mcp]"
```

Installed entry point:

```powershell
refute-mcp
```

Direct launch:

```powershell
python -m refute.mcp_server
```

A stdio MCP server normally appears to do nothing when launched manually. That is expected: it is waiting for an MCP host to communicate over stdin/stdout.

## MCP Inspector

For local development/testing:

```powershell
mcp dev src/refute/mcp_server.py
```

The MCP CLI's Inspector launcher may invoke `uv`. If `uv` is not available on Windows, install it only as development tooling:

```powershell
python -m pip install uv
```

`uv` is **not** required by the actual refute stdio server when an agent host launches `python -m refute.mcp_server` directly.

## OpenCode

Point a local stdio MCP server at the Python executable in the environment where `refute` is installed.

Example `opencode.jsonc` for Windows:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "refute": {
        "type": "local",
        "command": [
          "C:\\absolute\\path\\to\\refute\\.venv\\Scripts\\python.exe",
          "-m",
          "refute.mcp_server"
        ]
      }
    }
  }
}
```

Then an agent can be asked to:

```text
Inspect this PR with refute. If verification would execute third-party code,
ask me for approval before starting verification.
https://github.com/owner/repo/pull/123
```

## Claude Code

From the refute repository, an example local stdio registration on Windows is:

```powershell
claude mcp add refute -- .\.venv\Scripts\python.exe -m refute.mcp_server
```

For project-shared configuration, add the equivalent server command to the project's MCP configuration.

## Codex and other MCP hosts

The server is standard local stdio MCP rather than an OpenCode- or Claude-specific adapter. Any coding-agent host that can launch a local stdio MCP server can point at:

```text
<python executable> -m refute.mcp_server
```

The host owns the conversation and approval UX; `refute` owns deterministic execution, evidence collection, and verdict semantics.

## Recommended agent workflow

1. Call `inspect_pr(url)`.
2. Summarize the target repository, PR title, revisions, and execution implications to the human.
3. Ask for explicit permission before local execution.
4. Only after approval call `verify_pr(url, confirm_execution=true)` and retain its `job_id`.
5. Poll `get_verify_job(job_id)` until `status` is `complete` or `failed`.
6. Present the verdict together with the evidence rather than as an unsupported model judgment.
7. Use `get_run(run_id)` to revisit persisted evidence without rerunning third-party code.

## Scope and safety

The current real-repository path is intentionally narrow: **public GitHub PRs, Python repositories, and a detectable pytest test surface**. When the PR changes pytest files, refute can reuse those patch-authored tests as a deterministic reproduction against base and patch; if contract probes are unavailable, a bounded nearby-test adversary can prioritize existing tests while deterministic execution decides what actually happened.

`inconclusive` remains a valid outcome when the available evidence does not justify a stronger claim.

Dependency installation and target tests execute third-party code locally. The current implementation uses an isolated per-run Python environment but is **not** a strong OS/container security sandbox. Human approval is therefore required before `verify_pr` starts.