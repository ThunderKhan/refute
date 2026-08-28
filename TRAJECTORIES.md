# Agent Trajectories

This file records representative coding-agent trajectories used to build `refute` during the Frontier Engineering Challenge 2026.

The goal is to preserve the agent instruction, observable actions/tool results, feedback, retries, and human checkpoints without reconstructing them after the hackathon.

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

### Decision / learning

No LLM patch-verification logic was added in this milestone.

The project intentionally establishes deterministic execution and benchmark ground truth first, so later agentic components can be measured rather than assumed to help.

### Result

Milestone 1 establishes the deterministic spine needed for the next experiment: a static-review baseline evaluated against the same benchmark cases that the advanced workflow will use.
