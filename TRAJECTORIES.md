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

The code was pushed to `main`. Automated baseline tests were added, but the coding agent cannot execute the repository in its current network-isolated tool environment. Local verification by the human is therefore required before this milestone is considered closed.

### Next evidence needed

Run locally:

```powershell
python -m pytest
refute baseline benchmark\case_001 --provider ollama --model <installed-model>
```

Capture the test result and first real baseline verdict before expanding the benchmark or adding advanced verification logic.
