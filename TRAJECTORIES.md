# Agent Trajectories

This file records representative coding-agent trajectories used to build `refute` during the Frontier Engineering Challenge 2026.

The goal is to preserve the agent instruction, observable actions/tool results, feedback, retries, and human checkpoints without reconstructing them after the hackathon.

Portable normalized trace packages are stored under `traces/`. Those packages are provider-neutral, exclude secrets, and are intended to make later conversion to any required acquisition/submission format easier.

---

## trajectory-001 — Milestone 1 deterministic spine

### Human instruction

> "go ahead and implement milestone one I give you permission to push code to github"

### Agent objective

Implement the first runnable engineering milestone before adding any LLM-based patch reasoning: package configuration, verification data models, benchmark-case loader, deterministic command executor, case inspection CLI, three seed fixtures, and tests.

### Tool feedback / verification

The coding agent could not clone the repository in its execution sandbox because `github.com` could not be resolved. The human later verified locally that editable installation succeeded, `python -m pytest` returned `8 passed in 3.90s`, and `refute inspect benchmark\case_001` showed the expected original-fail/patched-pass behavior with persisted execution evidence.

### Result

Milestone 1 established the deterministic spine needed for later measured agentic work.

Normalized trace: `traces/trace-001-milestone-1/`.

---

## trajectory-002 — Static-review baseline

### Human instruction

> "alright go ahead and implement the next step"

### Agent objective

Implement a fair static baseline that sees issue text and a source diff only, without execution, reproduction, or benchmark-oracle leakage.

### Observable actions

The coding agent added local Ollama/OpenAI-compatible provider support, structured static-review prompting and parsing, persisted prompt/response/result artifacts, CLI support, and fake-LLM tests.

### Verification status

The human verified `12 passed in 3.33s` and ran `qwen3:0.6b` on the three seed cases. The baseline scored 0/3 on that preliminary set.

Normalized trace: `traces/trace-002-static-baseline/`.

---

## trajectory-003 — Revised Milestones 1–2: benchmark evaluator and architecture backbone

### Human instruction

> "okay go ahead and implement add whatever is not addeed for milestone 1 and 2 for our revised architecture"

### Agent objective

Turn the baseline into a reproducible batch experiment and introduce a real architecture with explicit orchestration and evidence provenance.

### Observable actions

The implementation added the ten-case benchmark, `refute eval-baseline`, aggregate metrics and reports, the evidence subsystem, the `VerificationRun` state machine, package boundaries, `ARCHITECTURE.md`, and automated tests.

### Verification status

The human ran the ten-case baseline with local Ollama `qwen3:0.6b` and observed:

- verdict accuracy: 10.0%,
- false acceptance rate: 57.1%,
- average runtime: 2.405 seconds.

This exact configuration is frozen as Baseline v1.

Normalized trace: `traces/trace-003-evaluator-architecture/`.

---

## trajectory-004 — Advanced Iteration 1: Investigator + runtime evidence

### Human instruction

> "okay let's implement this"

### Agent objective

Add structured semantic investigation plus deterministic execution of existing tests, while deliberately excluding generated reproduction and Challenger behavior.

### Observable actions

The coding agent added the Investigator, Iteration 1 verifier, evidence-constrained verdicting, capability flags, advanced batch evaluation, CLI commands, and a fake-LLM integration test.

### Verification status

The human verified a case-level run on `case_001`: original tests failed, patched tests passed, and the system returned `complete_fix`.

The human then ran the same ten-case benchmark with `qwen3:0.6b` and observed:

- verdict accuracy: 40.0%,
- false acceptance rate: 28.6%,
- average runtime: 5.641 seconds.

Compared with Baseline v1, this is +30 percentage points in verdict accuracy and approximately halves the false-acceptance rate, at the cost of additional runtime.

Normalized trace: `traces/trace-004-advanced-iteration-1/`.

---

## trajectory-005 — Advanced Iteration 2: generated reproduction + bounded retry

### Human instruction

> "implement it"

### Agent objective

Add the first explicit agent/tool feedback loop: generate a focused pytest reproduction, run it against the original implementation first, retry with execution feedback when it does not reproduce the bug, then run the same successful reproduction against the patched implementation.

### Observable actions

The coding agent:

- inspected the existing Investigator, orchestrator, evidence store, Iteration 1 verifier, evaluator, CLI, and tests,
- kept Iteration 1 intact for reproducible comparison,
- added `src/refute/agents/reproducer.py` with structured output parsing and conservative AST validation that blocks obvious dangerous modules/calls,
- added `src/refute/verify_v2.py` with bounded reproduction attempts, original-first validation, same-test patched execution, evidence persistence, existing-suite execution, and an evidence-constrained final verdict,
- updated the evaluator to support explicit Iterations 1 and 2 with separate report directories,
- updated the CLI so Iteration 2 is the default advanced path while `--iteration 1` remains available,
- added tests for generated-test safety checks and a deterministic two-attempt retry flow,
- created the normalized trace package while implementation was still in progress.

### Safety / execution decision

Generated tests execute only inside the controlled benchmark trees. The temporary test file is removed after each run, while the canonical generated source and tool output remain persisted in the evidence store. The Reproducer prompt forbids network, subprocess, shell, destructive file operations, and benchmark-oracle references; AST validation enforces a conservative subset of those restrictions mechanically.

### Experimental question

Does generated bug reproduction with execution-feedback retry improve on Advanced Iteration 1's 40.0% accuracy / 28.6% false acceptance without introducing unacceptable runtime cost?

### Verification status

Implementation is on `main`. Local verification is pending. Required commands:

```powershell
python -m pytest
refute verify benchmark\case_001 --provider ollama --model qwen3:0.6b --iteration 2
refute eval-advanced benchmark --provider ollama --model qwen3:0.6b --iteration 2
```

Normalized trace: `traces/trace-005-reproduction-loop/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh.

Each future trace should preserve, when available, the exact human instruction, objective, repository inspection/tool actions, edits/commit range, failures and retries, test/tool feedback, human checkpoints, measurable outcome, and model/provider metadata. Historical gaps must not be filled with invented details. Secrets and unrelated private data must never be recorded.
