# Agent Trajectories

This file records representative coding-agent trajectories used to build `refute` during the Frontier Engineering Challenge 2026.

The goal is to preserve the agent instruction, observable actions/tool results, feedback, retries, and human checkpoints without reconstructing them after the hackathon.

Portable normalized trace packages are stored under `traces/`. Those packages are provider-neutral, exclude secrets, and are intended to make later conversion to any required acquisition/submission format easier.

---

## trajectory-001 — Milestone 1 deterministic spine

### Human instruction

> "go ahead and implement milestone one I give you permission to push code to github"

### Agent objective

Implement the first runnable engineering milestone before adding any LLM-based patch reasoning:

1. package configuration,
2. verification data models,
3. benchmark-case loader,
4. deterministic command executor,
5. case inspection CLI,
6. three seed benchmark fixtures,
7. tests for the loader, executor, and fixture behavior.

### Human checkpoint

The human explicitly authorized direct pushes to `ThunderKhan/refute`.

### Observable actions

The coding agent inspected the existing repository and confirmed that the planning documents and empty Python scaffold were already present.

It then pushed the following implementation pieces to `main`:

- configured the package in `pyproject.toml`,
- defined `Verdict`, `VerificationCase`, `ExecutionResult`, and `InspectionResult`,
- implemented strict benchmark case loading and validation,
- implemented subprocess execution with captured stdout/stderr, exit status, duration, and timeout handling,
- added `refute inspect <case>` CLI behavior,
- persisted original/patched execution evidence into `artifacts/<case_id>/`,
- added seed cases for a complete fix, partial fix, and regression-introducing fix,
- added automated tests for case loading, command execution, timeout behavior, and benchmark execution shape,
- added a Python-focused `.gitignore`.

### Tool feedback / verification

Repository tree inspection through GitHub confirmed that the package, benchmark fixtures, and tests were present on `main` after the writes.

An attempt to clone the public repository into the execution sandbox for an independent local test run failed because the sandbox could not resolve `github.com`. This was an environment/network limitation rather than an observed project failure.

The human then verified the milestone locally on Windows:

- editable package installation completed successfully,
- `python -m pytest` returned `8 passed in 3.90s`,
- `refute inspect benchmark\case_001` reported the original fixture as failing and the patched fixture as passing,
- execution evidence was persisted under `artifacts/case_001/`.

### Decision / learning

No LLM patch-verification logic was added in this milestone.

The project intentionally establishes deterministic execution and benchmark ground truth first, so later agentic components can be measured rather than assumed to help.

### Result

Milestone 1 establishes the deterministic spine needed for the next experiment: a static-review baseline evaluated against the same benchmark cases that the advanced workflow will use.

Normalized trace: `traces/trace-001-milestone-1/`.

---

## trajectory-002 — Static-review baseline

### Human instruction

> "alright go ahead and implement the next step"

### Agent objective

Implement the intentionally simple baseline required for the baseline-versus-advanced experiment.

The baseline must make a patch verdict from issue text and a static code diff only. It must not execute code, reproduce the bug, or use the deterministic executor.

### Observable actions

The coding agent:

- inspected the current core models, CLI, and benchmark loader,
- added a provider abstraction supporting local Ollama and generic OpenAI-compatible chat endpoints using only the Python standard library,
- added `BaselineResult`,
- implemented deterministic source-diff construction from the original and patched benchmark trees,
- defined a strict static-review system prompt that explicitly forbids claims of execution,
- implemented structured JSON parsing into the five project verdict classes,
- persisted the exact baseline prompt, raw response, and parsed result under `artifacts/<case_id>/baseline/`,
- exposed the workflow as `refute baseline <case>`,
- added tests using a fake language model so baseline plumbing can be tested without network access or API credentials.

### Design checkpoint

The expected benchmark verdict is never included in the baseline prompt. This prevents ground-truth leakage into the experiment.

The baseline deliberately receives less capability than the eventual advanced workflow: it can reason statically but cannot execute tests or generate runtime evidence. This difference is intentional and must be disclosed in the final comparison.

### Verification status

The human verified this milestone locally:

- `python -m pytest` returned `12 passed in 3.33s`,
- local Ollama model `qwen3:0.6b` was used for all three seed cases,
- case 001 ground truth `complete_fix` was predicted `partial_fix`,
- case 002 ground truth `partial_fix` was predicted `complete_fix`,
- case 003 ground truth `regression_introduced` was predicted `partial_fix`.

The initial static baseline therefore scored 0/3 on the seed set. This is only an early signal and is not treated as a final benchmark claim.

Normalized trace: `traces/trace-002-static-baseline/`.

---

## trajectory-003 — Revised Milestones 1–2: benchmark evaluator and architecture backbone

### Human instruction

> "okay go ahead and implement add whatever is not addeed for milestone 1 and 2 for our revised architecture"

### Agent objective

Complete the missing pieces of the revised first two milestones without prematurely implementing the advanced semantic agents.

The round targeted two things:

1. turn the baseline into a reproducible batch experiment over a broader benchmark,
2. introduce a real system architecture with an orchestrator and first-class evidence provenance.

### Observable actions

The coding agent created a temporary implementation branch, then added and fast-forwarded the completed work to `main`.

The implementation added:

- `refute eval-baseline <benchmark_dir>` for one-command batch evaluation,
- aggregate verdict accuracy, false-acceptance rate, per-class accuracy, confusion matrix, runtime metadata and persisted reports,
- `artifacts/eval/baseline/summary.json`, `cases.jsonl`, and `report.md`,
- benchmark expansion from 3 to 10 controlled cases covering complete, partial, ineffective, regression-introducing and inconclusive outcomes,
- an `evidence` package with typed evidence records and an append-only JSONL provenance store,
- a `VerificationRun` orchestrator state machine with explicit legal stage transitions,
- package boundaries for `agents`, `runtime`, `providers`, `benchmark`, and `evidence`,
- `ARCHITECTURE.md` documenting the design thesis and advanced target flow,
- automated tests for the evaluator, evidence store, orchestrator, and ten-case benchmark catalog.

### Architecture decision

The project deliberately does not turn every architectural role into a separate LLM call.

The current invariant is:

> Agents propose and reason. Deterministic tools observe. Evidence constrains the verdict.

The advanced investigator, reproducer, challenger and verifier remain future capabilities. Milestone 2 only establishes the stable boundaries they will plug into.

### Verification status

The human ran the ten-case baseline evaluation locally with:

```powershell
refute eval-baseline benchmark --provider ollama --model qwen3:0.6b
```

Observed result:

- cases: 10,
- verdict accuracy: 10.0%,
- false acceptance rate: 57.1%,
- average runtime: 2.405 seconds.

This exact configuration is frozen as Baseline v1 so later advanced iterations can be compared without tuning the baseline after seeing its failures.

Normalized trace: `traces/trace-003-evaluator-architecture/`.

---

## trajectory-004 — Advanced Iteration 1: Investigator + runtime evidence

### Human instruction

> "okay let's implement this"

### Agent objective

Implement the first advanced verification path while preserving experimental isolation. This iteration adds structured semantic investigation, deterministic execution of existing tests, evidence provenance, and an evidence-constrained verdict. It deliberately excludes generated reproduction and Challenger behavior.

### Observable actions

The coding agent inspected the existing orchestrator, evidence subsystem, executor, CLI, and benchmark evaluator before editing. It then:

- added `src/refute/agents/investigator.py` with a structured Investigator schema and parser,
- extended the run state machine so Iteration 1 can skip generated reproduction while retaining that branch for later rounds,
- added `src/refute/verify.py` to orchestrate investigation, original execution, patched execution, evidence persistence, and final evidence-constrained verdict generation,
- added explicit capability flags so a run cannot imply that generated reproduction or Challenger checks occurred when they did not,
- added `src/refute/benchmark/advanced_evaluator.py` for ten-case Advanced Iteration 1 evaluation,
- exposed `refute verify` and `refute eval-advanced`,
- added a fake-LLM integration test covering the two model calls, runtime execution, evidence JSONL, result manifest, and capability declarations,
- created the normalized trace package during the implementation round.

### Experimental question

Does structured issue understanding plus deterministic runtime evidence improve verdict accuracy and reduce false acceptance relative to frozen Baseline v1?

### Verification status

Implementation is on `main`. Local verification is pending. The human should run:

```powershell
python -m pytest
refute verify benchmark\case_001 --provider ollama --model qwen3:0.6b
refute eval-advanced benchmark --provider ollama --model qwen3:0.6b
```

The trace must remain marked pending until those outputs are observed rather than inferred.

Normalized trace: `traces/trace-004-advanced-iteration-1/`.

---

## Ongoing trace-capture rule

From this point onward, every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh.

Each future trace should preserve, when available:

- the exact human instruction,
- agent objective and plan,
- repository inspection and tool actions,
- edits or source commit range,
- failures, retries and corrections,
- test/tool feedback,
- human checkpoints,
- final measurable outcome,
- model/provider metadata when relevant.

Historical gaps must not be backfilled with invented details. Secrets and unrelated private data must never be recorded.
