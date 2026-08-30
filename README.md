<div align="center">

<img src="assets/refute-hero.png" alt="refute — evidence-backed patch verification" width="100%">

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Core Runtime Dependencies](https://img.shields.io/badge/core%20runtime%20dependencies-zero-00b894)
![Benchmark](https://img.shields.io/badge/Benchmark%20v2-10%2F10%20correct-2ea44f)
![Holdout](https://img.shields.io/badge/Post--freeze%20holdout-83.3%25-2ea44f)
![False Acceptance](https://img.shields.io/badge/Benchmark%20FAR-0.0%25-2ea44f)
![MCP](https://img.shields.io/badge/MCP-stdio-8b5cf6)
![License](https://img.shields.io/badge/license-MIT-2ea44f)

**Frontier Engineering Challenge 2026**

[Why refute?](#why-refute) · [How it works](#how-it-works) · [Real PRs](#real-github-pr-workflow) · [Measured results](#measured-results) · [Post-freeze validation](#post-freeze-validation) · [Quick start](#quick-start) · [MCP](#coding-agent-integration-mcp)

</div>

---

## Why refute?

Software patches are often reviewed by asking whether the diff *looks* correct. That is not the same as establishing that the bug is actually fixed.

A patch can repair the exact example from the issue while leaving an adjacent boundary broken, fix one behavior while regressing another, make a narrow test pass without satisfying the broader public contract, or simply look plausible to a language model without executable evidence.

`refute` takes a stricter approach:

> **Treat every proposed fix as a hypothesis, then actively try to falsify it.**

The system runs original and patched code, establishes whether the reported trigger is actually repaired, challenges nearby behavior, and returns a five-way verdict constrained by observed evidence.

### A concrete falsification

`case_002` is the simplest example: the patch repairs the lower boundary of an inclusive `0..100` contract, but still rejects `100`. The existing public test passes; refute derives and executes the missing upper-boundary probe and returns `partial_fix`.

<p align="center">
  <img src="assets/refute-case-study.png" alt="case_002 falsification walkthrough showing a partial fix discovered by refute" width="100%">
</p>

---

## How it works

The governing design rule is:

> **Agents prioritize. Deterministic tools observe. Evidence constrains the verdict.**

<p align="center">
  <img src="assets/refute-architecture.png" alt="refute architecture: agents prioritize, deterministic tools observe, evidence constrains the verdict" width="100%">
</p>

The final Benchmark v2 architecture deliberately gives the model a narrow job. It does **not** author arbitrary pytest code or invent the final verdict. Mechanically recognizable public requirements are compiled into deterministic probes; deterministic execution decides what happened.

Iteration 5 retains a bounded model planner that can prioritize valid probe IDs, but the post-freeze ablation and holdout show an important result: **within the tested contract domain, the planner did not improve verdict accuracy over deterministic probe order.** The main measured gain came from moving mechanically derivable semantics out of model generation and into deterministic evidence.

For compatible real GitHub PRs, refute adds a product-facing reproduction path: patch-authored changed pytest tests can be replayed against the base revision to establish the reported trigger, and a bounded nearby-test adversary can prioritize existing tests when the deterministic contract compiler has no matching vocabulary. That is where semantic agentic prioritization remains useful: selecting among ambiguous, pre-existing test candidates rather than inventing executable truth.

---

## Verdict model

| Verdict | Meaning |
|---|---|
| `complete_fix` | the reported trigger is repaired and enough independent nearby checks also survive |
| `partial_fix` | the reported trigger is repaired, but a closely related requirement still fails |
| `ineffective_fix` | the patch does not repair the observed failure |
| `regression_introduced` | the patch repairs the reported trigger but breaks behavior that worked before |
| `inconclusive` | the available evidence is insufficient for a stronger claim |

`inconclusive` is a first-class result. Refute prefers defensible uncertainty over fabricated certainty.

<p align="center">
  <img src="assets/refute-verdict-system.png" alt="refute five-way verdict system and evidence patterns" width="100%">
</p>

---

## Real GitHub PR workflow

The dashboard's primary developer workflow accepts a **public GitHub pull-request URL** for a compatible Python/pytest repository.

```text
public GitHub PR
      ↓
inspect PR + public contract
      ↓
clone base/head revisions
      ↓
provision isolated per-run Python environment
      ↓
replay changed pytest tests on base + patch when available
      ↓
reported trigger repaired?
      ↓ yes
compile deterministic contract probes
      ↓ when unavailable
agent prioritizes bounded nearby existing tests
      ↓
deterministic execution
      ↓
evidence-backed verdict
```

A real run against `vitali87/pr-split#56` established a repaired trigger by replaying patch-authored tests against the base revision (`5 failed, 47 passed`) and patch (`52 passed`). The nearby adversary considered 40 existing candidates, selected three without fallback, and all three survived on both revisions. Refute therefore remained `inconclusive` rather than falsely claiming a complete fix.

That real-PR result is a product demonstration, **not** part of the frozen Benchmark v2 accuracy claim.

### Safety boundary

Dependency installation and repository tests execute third-party code locally. Refute creates an isolated per-run Python environment and requires explicit human acknowledgement before execution, but it is **not** a strong OS/container sandbox. Use only repositories you are willing to execute.

---

## Measured results

The development benchmark is **Benchmark v2**, a controlled ten-case benchmark with public case material separated from evaluator-only verdicts and hidden checks. Frozen measurements use local Ollama with `qwen3:0.6b` at temperature `0`.

| System | Verdict accuracy | False acceptance rate | Avg runtime |
|---|---:|---:|---:|
| Static Baseline v2 | 10.0% | 57.1% | 2.527s |
| Test-first ablation 2.4 | 60.0% | 57.1% | 0.929s |
| Challenger 3 | 40.0% | 0.0% | 14.774s |
| Grounded Challenger 3.1 | 30.0% | 0.0% | 20.438s |
| Contract IDs 3.2 | 30.0% | 0.0% | 25.966s |
| Contract Critic 3.3 | 30.0% | 0.0% | 27.624s |
| Intent-first 4 | 30.0% | 0.0% | 13.026s |
| **Deterministic contract probes 5** | **100.0%** | **0.0%** | **5.077s** |

<p align="center">
  <img src="assets/refute-results-comparison.png" alt="refute results comparison between Baseline v2 and Iteration 5" width="100%">
</p>

### Frozen Iteration 5 result

- **10 / 10 correct verdicts**
- **0 evaluation errors**
- **0.0% false acceptance rate**
- **4 executable counterexamples discovered**
- **57.1% Challenger case yield**
- **0 challenge-generation failures**
- **0 planner fallbacks**
- **5.077s average runtime per case**

> **Important:** 100% is the measured result on the controlled ten-case Benchmark v2 development set. It is not a claim of universal patch-verification accuracy.

---

## Post-freeze validation

Benchmark v2 is oracle-separated, but it was still used during system development. To test generalization more honestly, the verifier was frozen first and then evaluated on a new **12-case Holdout v1** that was authored and hashed after Iteration 5 was frozen.

Public Holdout v1 SHA-256:

```text
c2604717e69fb99c2d30e17ee4f586d4463e3bd032e55344684e9db9992b5cb1
```

The holdout audit confirmed that public case material contains no verdict oracle and that the 12 public cases match the 12 evaluator-only oracle entries.

### Holdout v1 results

| System | Completed | Verdict accuracy | FAR | Avg runtime |
|---|---:|---:|---:|---:|
| Static LLM baseline | 10 / 12 | **33.3% conservative** | 30.0% | 16.883s |
| Deterministic probe order, no planner | 12 / 12 | **83.3%** | 20.0% | 2.698s |
| Frozen Iteration 5 + planner | 12 / 12 | **83.3%** | 20.0% | 9.989s |

The static baseline timed out on two cases (`holdout_006`, `holdout_012`). The headline **33.3%** score is conservative: those provider errors remain in the 12-case denominator. Accuracy over the 10 completed baseline cases was **40.0%**.

Both deterministic probe ordering and Iteration 5 classified **10 of 12 unseen cases correctly**. Both missed `holdout_010` and `holdout_012`, producing `complete_fix` where the evaluator expected `partial_fix`.

This exposes a real generalization gap relative to the development benchmark:

- verdict accuracy: **100.0% → 83.3%**
- false acceptance rate: **0.0% → 20.0%**

That result is preserved rather than tuned away.

### Agent-prioritization ablation

After Iteration 5 was frozen, a controlled ablation removed the LLM probe planner while keeping the same deterministic contract compiler, probe budget (`2`), execution logic, classification rules, and verdict thresholds.

On Benchmark v2, deterministic ordering reproduced the full **100.0% accuracy / 0.0% FAR** result and all four counterexamples with no model calls. On Holdout v1, deterministic ordering again matched Iteration 5 at **83.3% accuracy / 20.0% FAR**, while running substantially faster.

The supported conclusion is therefore narrower and stronger:

> **Within the tested contract domain, the deterministic contract compiler is the primary source of verification value. Model-based probe prioritization has not shown measurable verdict improvement under the tested two-probe budget.**

The broader product still uses agentic prioritization where ambiguity is real, particularly bounded selection among nearby existing tests in compatible real repositories.

See [`docs/HOLDOUT_V1_PROTOCOL.md`](docs/HOLDOUT_V1_PROTOCOL.md) and [`docs/AGENT_ABLATION.md`](docs/AGENT_ABLATION.md) for the frozen protocol and full interpretation.

---

## The experiment that mattered

The strongest improvement did **not** come from a better prompt.

Early iterations gave the model increasing responsibility: generating pytest source, grounding tests in issue text, selecting contract IDs, and using a separate Critic. Safety improved, but accuracy stalled around 30% and runtime increased. Iteration 4 removed Python generation but still asked the model to invent test semantics; accuracy remained 30%.

Iteration 5 changed the responsibility boundary:

```text
before
model invents test semantics + code
        ↓
execution tries to validate them

final
public contract
        ↓
deterministic probe compiler
        ↓
bounded ordering / prioritization
        ↓
deterministic execution
```

That structural change produced the first clean **10/10 Benchmark v2** result. The later ablation showed that, for the supported contract vocabulary, the deterministic compiler rather than the planner accounted for that benchmark gain.

<p align="center">
  <img src="assets/refute-engineering-journey.png" alt="refute engineering journey from prompt-heavy experiments to deterministic evidence-backed verification" width="100%">
</p>

See [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md) for the measured iteration history, negative experiments, ablation, and post-freeze holdout.

---

## Benchmark integrity

Benchmark v1 exposed too much verdict information through public tests. A deterministic workflow reached 100% without meaningful agent participation, so that result was treated as a **benchmark failure**, not a success.

Benchmark v2 separates public inputs from evaluator-only scoring material:

```text
benchmark_v2/case_XXX/
  case.json          public metadata; no expected verdict
  issue.md           public bug contract
  original/
  patched/

eval/benchmark_v2/
  oracles.json       evaluator-only verdicts
  hidden_tests.json  evaluator-only nearby behavior
```

The Iteration 5 verification path does not load `oracles.json` or `hidden_tests.json`. Check the separation directly:

```powershell
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
```

Expected integrity result:

```text
AUDIT PASSED: public cases are oracle-free and hidden behavior is separated as designed.
```

Holdout v1 applies the same public/evaluator separation and additionally records a SHA-256 digest before evaluation.

---

## Quick start

### Requirements

- Python 3.11+
- Ollama
- `qwen3:0.6b`
- Node/npm only for the dashboard frontend

### Install

```powershell
git clone https://github.com/ThunderKhan/refute.git
cd refute
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ollama pull qwen3:0.6b
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
python -m pytest
```

The frozen Iteration 5 measurement point recorded `72 passed in 63.16s`. After dashboard, real-PR, MCP, holdout, and evaluator hardening, the project suite was locally verified as **93 passed in 68.98s**. The later test count does not alter the frozen benchmark metric.

### Verify the flagship benchmark case

```powershell
refute verify benchmark_v2\case_002 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

Representative result:

```text
original tests: FAIL
patched tests:  PASS
challenge outcome: remaining_requirement_counterexample
verdict: partial_fix
```

### Reproduce the final benchmark

```powershell
refute eval-advanced benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

### Build and audit the post-freeze holdout

```powershell
python scripts/build_holdout_v1.py
python scripts/audit_holdout_v1.py
```

The documented holdout protocol and expected digest are in [`docs/HOLDOUT_V1_PROTOCOL.md`](docs/HOLDOUT_V1_PROTOCOL.md).

For the exact clean-environment procedure and expected per-case Benchmark v2 verdicts, see [`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md).

### Run the dashboard

```powershell
python -m refute.dashboard_server
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/verify`.

---

## Coding-agent integration (MCP)

Refute exposes a local **stdio MCP server**, allowing coding-agent hosts to use the same verification engine without going through the dashboard.

The proven flow is:

```text
inspect_pr(url)
      ↓
human approves local execution
      ↓
verify_pr(..., confirm_execution=true) → job_id
      ↓
get_verify_job(job_id) until complete
      ↓
get_run(run_id)
```

`verify_pr` is asynchronous so long dependency/test runs do not depend on one MCP request remaining open.

Start the server with:

```powershell
python -m refute.mcp_server
```

or configure a compatible MCP host to launch:

```text
<python executable> -m refute.mcp_server
```

See [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) for OpenCode, Claude Code, Codex-style host guidance, MCP Inspector testing, and the explicit execution-approval contract.

---

## Evidence and reproducibility

Every advanced run persists evidence under:

```text
artifacts/runs/<run_id>/
```

Aggregate Benchmark v2 outputs are written to:

```text
artifacts/eval/advanced_iteration_5_benchmark_v2/
  summary.json
  cases.jsonl
  cases.partial.jsonl
  report.md
```

Post-freeze validation is documented under:

```text
docs/HOLDOUT_V1_PROTOCOL.md
docs/AGENT_ABLATION.md
```

Development trajectories are preserved under [`traces/`](traces/). The final Iteration 5 package contains normalized observable actions, metadata, a summary, human instruction/checkpoint material, and the frozen local verification transcript. No hidden chain-of-thought is reconstructed.

---

## Scope

### Supported in the hackathon product

- controlled Python Benchmark v2 cases;
- post-freeze synthetic Holdout v1 evaluation;
- public GitHub PR inspection;
- compatible public Python/pytest PR verification;
- isolated per-run Python dependency environment for target repositories;
- patch-authored changed-test reproduction against base and patch when available;
- deterministic public-contract probe compilation for a deliberately small contract vocabulary;
- bounded agent prioritization of valid probes or nearby existing tests;
- deterministic execution and evidence-backed five-way verdicts;
- local dashboard/API;
- local stdio MCP integration;
- local Ollama / provider abstraction.

### Not claimed

- arbitrary programming-language support;
- universal GitHub repository compatibility;
- formal correctness proofs;
- strong container/VM isolation for untrusted code;
- authoritative security review;
- automatic merging or deployment of patches;
- universal 100% patch-verification accuracy;
- that the LLM planner improves accuracy within the current deterministic contract-probe domain.

---

## Project structure

```text
src/refute/
  agents/                  agent roles + deterministic probe components
  benchmark/               evaluation and oracle-loading code
  cli.py                   command-line interface
  dashboard_server.py      local dashboard API
  github_pr.py             public PR inspection + workspace preparation
  real_repo_adversary.py   bounded nearby existing-test adversary
  mcp_server.py            stdio MCP tools + async verification jobs
  executor.py              deterministic command execution
  evidence/                persisted evidence records
  orchestrator.py          verification run state machine
  verify_v5.py             frozen Iteration 5 verifier

frontend/                  React/Vite developer dashboard
benchmark_v2/              generated oracle-free development benchmark
holdout_v1/                generated post-freeze public holdout cases
eval/benchmark_v2/         evaluator-only Benchmark v2 oracles + hidden checks
eval/holdout_v1/           evaluator-only Holdout v1 oracles
scripts/                   benchmark/holdout build + integrity audit tools
tests/                     unit and regression tests
traces/                    normalized development trajectories
docs/                      MCP, holdout, and ablation documentation
assets/                    README visual assets
```

---

## Documentation

| Document | Purpose |
|---|---|
| [`PROBLEM_STATEMENT.md`](PROBLEM_STATEMENT.md) | user problem and product thesis |
| [`PRD.md`](PRD.md) | product requirements and original design goals |
| [`MVP.md`](MVP.md) | supported scope, milestones, and acceptance criteria |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | verification architecture and component boundaries |
| [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md) | measured experiments, regressions, ablations, and design decisions |
| [`TRAJECTORIES.md`](TRAJECTORIES.md) | human-readable index of coding-agent trajectories |
| [`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md) | frozen benchmark + current product reproduction procedure |
| [`docs/HOLDOUT_V1_PROTOCOL.md`](docs/HOLDOUT_V1_PROTOCOL.md) | post-freeze holdout protocol, digest, and results |
| [`docs/AGENT_ABLATION.md`](docs/AGENT_ABLATION.md) | controlled no-planner ablation and interpretation |
| [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) | MCP tools, safety contract, and host setup |
| [`traces/`](traces/) | normalized per-iteration execution/development evidence |

---

## Design principle

> **When requirements are mechanically derivable, deterministic evidence should own them completely. Agentic reasoning should be reserved for ambiguity that deterministic machinery cannot represent.**

The project started with the simpler lesson that the model needed less responsibility. The measured ablation and post-freeze holdout sharpened that further: deterministic tools should own mechanically observable truth, while agents should be used for bounded semantic prioritization where deterministic structure runs out.

---

## License

MIT
