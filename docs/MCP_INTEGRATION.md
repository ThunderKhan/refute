# refute MCP integration

`refute` exposes a local Model Context Protocol (MCP) server so coding agents can inspect and verify pull requests without going through the dashboard.

The server uses MCP over **stdio**. The host starts `refute-mcp` as a child process and receives structured tool results.

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

Runs the real GitHub verification workflow and returns structured evidence.

This tool can clone third-party code, create an isolated Python environment, install the target repository's declared dependencies, and execute its pytest tests locally. For that reason `confirm_execution` defaults to `false` and the tool refuses to run until the human explicitly approves local execution.

Input example:

```json
{
  "url": "https://github.com/owner/repo/pull/123",
  "confirm_execution": true,
  "provider": "ollama",
  "model": "qwen3:0.6b"
}
```

The returned object includes the verdict, reason, base/patch execution evidence, contract probes, nearby-test adversary evidence when used, counterexample count, and evidence path.

### `get_run`

Read-only. Reloads a previously recorded run by `run_id` without executing repository code.

## Install

For development, the existing dev extra installs the MCP SDK:

```powershell
python -m pip install -e ".[dev]"
```

For an integration-only install:

```powershell
python -m pip install -e ".[mcp]"
```

The installed entry point is:

```powershell
refute-mcp
```

You can also launch it directly:

```powershell
python -m refute.mcp_server
```

A stdio MCP server normally appears to do nothing when launched manually. That is expected: it is waiting for an MCP host to communicate over stdin/stdout.

## OpenCode

OpenCode supports local stdio MCP servers. Point its local server command at the Python executable in the environment where `refute` is installed.

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
ask me for approval before calling verify_pr.
https://github.com/owner/repo/pull/123
```

## Claude Code

Claude Code can add a local stdio MCP server from the CLI. From the refute repository, an example on Windows is:

```powershell
claude mcp add refute -- .\.venv\Scripts\python.exe -m refute.mcp_server
```

For a project-shared configuration, add the server with project scope or put the equivalent command in `.mcp.json`.

The same safety rule applies: `inspect_pr` is read-only; `verify_pr` requires explicit `confirm_execution=true` after the user approves running target-repository code locally.

## Codex and other MCP hosts

The server is standard local stdio MCP rather than an OpenCode- or Claude-specific adapter. Any coding-agent host that can launch a local stdio MCP server can point at:

```text
<python executable> -m refute.mcp_server
```

That keeps the integration surface small: the host owns the conversation and approval UX; `refute` owns deterministic execution, evidence collection, and verdict semantics.

## Recommended agent workflow

1. Call `inspect_pr(url)`.
2. Summarize the target repository, PR title, revisions, and execution implications to the human.
3. Ask for explicit permission before local execution.
4. Only after approval call `verify_pr(url, confirm_execution=true)`.
5. Present the verdict together with the evidence, not as an unsupported model judgment.
6. Use `get_run(run_id)` to revisit recorded evidence without rerunning third-party code.

## Scope

The current real-repository path is intentionally narrow: public GitHub PRs, Python repositories, and a detectable pytest test surface. `inconclusive` remains a valid outcome when the available evidence does not justify a stronger claim.
