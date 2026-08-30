# Coding-Agent Trace Archive

This directory preserves normalized, portable traces of meaningful coding-agent work performed while building `refute`.

The archive serves two purposes:

1. satisfy the hackathon requirement to preserve representative agent trajectories with instructions, tool feedback, retries and human checkpoints;
2. retain high-quality coding-agent interaction records that can be converted to a third-party acquisition format later if requested.

## Trace policy

A trace is created for a substantial engineering round, not for every tiny edit. Each trace should preserve the task, observable agent actions, important tool feedback, human verification, decisions, and outcome.

We do not fabricate missing raw events. Historical traces contain only details supported by the conversation, Git history, tool results, or human-provided verification output. Some retrospective traces are intentionally compact when only a subset of those records was preserved. Future traces should be captured contemporaneously as work happens.

Secrets, credentials, API keys, private third-party content, and unrelated personal data must never be included. Hidden chain-of-thought is not part of this archive; normalized events record only observable instructions, actions, outputs, checkpoints, and decisions.

## Current traces

| Trace | Engineering round | Status |
|---|---|---|
| `trace-001-milestone-1` | Deterministic verification spine | verified locally |
| `trace-002-static-baseline` | Static LLM review baseline | verified locally |
| `trace-003-evaluator-architecture` | Batch evaluator + architecture backbone | baseline experiment verified |
| `trace-004-advanced-iteration-1` | Investigator + runtime evidence | verified locally |
| `trace-005-reproduction-loop` | Generated reproduction + recovery | verified locally |
| `trace-006-iteration-2-1` | Discriminating reproduction semantics | verified locally |
| `trace-007-iteration-2-2` | Evidence weighting + stagnation stop | verified locally |
| `trace-008-iteration-2-3` | Deterministic test-delta engine | verified locally; one benchmark provider error |
| `trace-009-iteration-2-4` | Test-first routing + benchmark diagnosis | verified locally |
| `trace-010-benchmark-v2` | Oracle-separated Benchmark v2 redesign | verified; Baseline v2 and ablation measured |
| `trace-011-iteration-3` | Conditional Challenger | verified locally |
| `trace-012-iteration-3-1` | Exact-quote grounding | compact retrospective trace; verified locally |
| `trace-013-iteration-3-2` | Deterministic contract IDs | compact retrospective trace; verified locally |
| `trace-014-iteration-3-3` | Contract-entailment Critic | compact retrospective trace; verified locally |
| `trace-015-iteration-4` | Intent-first Challenger | verified locally |
| `trace-016-iteration-5` | Deterministic contract probes | **final frozen benchmark trace; verified locally** |

`TRAJECTORIES.md` is the human-readable index for all sixteen rounds. The final Iteration 5 directory contains `human_instruction.md`, `metadata.json`, `actions.jsonl`, `summary.md`, and the frozen human verification transcript.

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

Each trace's `metadata.json` may record a source commit range when known. The actual repository diff remains available from Git history and is not duplicated here unless a later acquisition format explicitly requires a patch file.
