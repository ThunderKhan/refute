# Coding-Agent Trace Archive

This directory preserves normalized, portable traces of meaningful coding-agent work performed while building `refute`.

The archive serves two purposes:

1. satisfy the hackathon requirement to preserve representative agent trajectories with instructions, tool feedback, retries and human checkpoints;
2. retain high-quality coding-agent interaction records that can be converted to a third-party acquisition format later if requested.

## Trace policy

A trace is created for a substantial engineering round, not for every tiny edit. Each trace should preserve the task, observable agent actions, important tool feedback, human verification, decisions, and outcome.

We do not fabricate missing raw events. Historical traces contain only details supported by the conversation, Git history, tool results, or human-provided verification output. Future traces should be captured contemporaneously as work happens.

Secrets, credentials, API keys, private third-party content, and unrelated personal data must never be included.

## Current traces

| Trace | Engineering round | Status |
|---|---|---|
| `trace-001-milestone-1` | Deterministic verification spine | verified locally |
| `trace-002-static-baseline` | Static LLM review baseline | verified locally |
| `trace-003-evaluator-architecture` | Batch evaluator + architecture backbone | implementation complete; baseline experiment verified |

## Normalized event format

`actions.jsonl` uses one JSON object per event. Common fields are:

```json
{
  "step": 1,
  "actor": "human | agent | tool",
  "action": "instruction | inspect | create_file | update_file | test | run | feedback | decision",
  "target": "optional file/command/component",
  "result": "observable outcome",
  "source": "conversation | github | human_verification"
}
```

This is intentionally provider-neutral so the traces can be transformed later without depending on a ChatGPT-specific export format.

## Source commit ranges

Each trace's `metadata.json` records a source commit range. The actual repository diff remains available from Git history and is not duplicated here unless a later acquisition format explicitly requires a patch file.
