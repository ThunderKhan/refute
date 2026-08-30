<div align="center">

# refute

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Runtime Dependencies](https://img.shields.io/badge/runtime%20dependencies-zero-00b894)
![Benchmark](https://img.shields.io/badge/Benchmark%20v2-10%2F10%20correct-2ea44f)
![False Acceptance](https://img.shields.io/badge/false%20acceptance-0.0%25-2ea44f)
![License](https://img.shields.io/badge/license-MIT-2ea44f)

**Frontier Engineering Challenge 2026**

[Why refute?](#why-refute) · [How it works](#how-it-works) · [Verdicts](#verdict-model) · [Measured results](#measured-results) · [Quick start](#quick-start) · [Evidence](#evidence-and-reproducibility) · [Docs](#documentation)

</div>

---

## Why refute?

Software patches are often reviewed by asking whether the diff *looks* correct. That is not the same as establishing that the bug is actually fixed.

A patch can:

- repair the exact example from the issue while leaving the adjacent boundary broken;
- fix one behavior while silently regressing another valid behavior;
- make an existing test pass without satisfying the full public contract;
- or appear plausible to a language model despite having no executable evidence behind it.

`refute` takes a stricter approach:

> **Treat every proposed fix as a hypothesis, then actively try to falsify it.**

The system runs the original and patched code, derives nearby checks from the public issue contract, executes those checks against both versions, and returns a verdict that is constrained by observed evidence.

### A concrete falsification

`case_002` is the simplest example of the core idea: the reported lower boundary is repaired, but the same public contract still requires the upper boundary to work.

---

## How it works

The final architecture separates semantic prioritization from mechanically observable truth.

The governing design rule is:

> **Agents prioritize. Deterministic tools observe. Evidence constrains the verdict.**

The final workflow deliberately gives the model a narrow job. It does **not** author arbitrary pytest code or invent the final verdict. Mechanically derivable checks are compiled deterministically from the public issue contract; the agent only prioritizes which valid probes to try first.

At a high level:

```text
issue + original + patched code
              |
              v
     run public tests
      on both versions
              |
              v
      compare test delta
              |
       +------+------+
       |             |
 mechanically     reported trigger
  decisive?       appears repaired
       |             |
       v             v
    verdict     public-contract
               probe compiler
                    |
                    v
               bounded probe pool
                    |
                    v
              agent prioritizes
                 probe IDs
                    |
                    v
             deterministic pytest
                execution
             original + patched
                    |
                    v
          evidence-backed verdict
```

---

## Verdict model

Every run resolves to one of five outcomes. The verdict is determined by the observed evidence pattern, not by an unconstrained model judgment.

| Verdict | Meaning |
|---|---|
| `complete_fix` | the reported trigger is repaired and enough independent nearby checks also survive |
| `partial_fix` | the reported trigger is repaired, but a closely related requirement still fails |
| `ineffective_fix` | the patch does not repair the observed failure |
| `regression_introduced` | the patch repairs the reported trigger but breaks behavior that worked before |
| `inconclusive` | the available evidence is insufficient for a stronger claim |

`inconclusive` is a first-class result. `refute` is designed to prefer defensible uncertainty over fabricated certainty.

---

## Measured results

The final evaluation uses **Benchmark v2**, a controlled ten-case benchmark with public case material separated from evaluator-only verdicts and hidden checks.

All measurements below use local Ollama with `qwen3:0.6b` at temperature `0`.

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

### Frozen Iteration 5 result

- **10 / 10 correct verdicts**
- **0 evaluation errors**
- **0.0% false acceptance rate**
- **4 executable counterexamples discovered**
- **57.1% Challenger case yield**
- **0 challenge-generation failures**
- **0 planner fallbacks**
- **5.077s average runtime per case**

The recovered failures cover four different bug shapes:

- an inclusive upper-boundary miss;
- an internal-space preservation regression;
- tiny truncation limits that still violate the stated invariant;
- and exception behavior accidentally swallowed by a patch.

> **Important:** 100% is the measured result on this ten-case controlled benchmark. It is not a claim of universal patch-verification accuracy.

---

## The experiment that mattered

The strongest improvement did **not** come from a better prompt.

Early iterations gave the model increasing responsibility: generating pytest source, grounding tests in issue text, selecting contract IDs, and then having a second model criticize generated tests. Those systems became safer, but accuracy stalled and runtime increased.

Iteration 4 removed Python generation but still asked the model to invent test semantics. Accuracy remained at 30%.

Iteration 5 changed the responsibility boundary:

```text
before
model invents test semantics + code
        |
        v
execution tries to validate them

final
public contract
        |
        v
deterministic probe compiler
        |
        v
agent prioritizes valid probes
        |
        v
deterministic execution
```

That change produced the first clean **10/10 Benchmark v2** result.

The project therefore preserves failed and removed experiments rather than hiding them. See [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md) for the complete measured iteration history.

---

## Benchmark integrity

Benchmark v1 exposed too much information through its public test suites. A deterministic workflow reached 100% without meaningful agent participation, so that result was treated as a **benchmark failure**, not a success.

Benchmark v2 separates public verification inputs from evaluator-only scoring material:

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

The Iteration 5 verification path does **not** load `oracles.json` or `hidden_tests.json`. Those files are used only after a verdict has been produced, to score the benchmark.

The separation can be checked directly:

```powershell
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
```

Expected integrity result:

```text
AUDIT PASSED: public cases are oracle-free and hidden behavior is separated as designed.
```

---

## Quick start

### Requirements

- Python 3.11+
- Ollama
- `qwen3:0.6b`

### Install

```powershell
git clone https://github.com/ThunderKhan/refute.git
cd refute
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ollama pull qwen3:0.6b
```

### Build and audit the benchmark

```powershell
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
python -m pytest
```

Frozen test-suite verification:

```text
72 passed in 63.16s
```

### Verify one patch

```powershell
refute verify benchmark_v2\case_002 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

Representative result:

```text
case: case_002
original tests: FAIL
patched tests:  PASS
challenge outcomes: remaining_requirement_counterexample
verdict: partial_fix
```

### Reproduce the final benchmark

```powershell
refute eval-advanced benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

Expected headline metrics:

```text
completed cases: 10
errors: 0
verdict accuracy: 100.0%
false acceptance rate: 0.0%
challenge counterexamples: 4
probe planner fallback cases: 0
average runtime: 5.077s
```

For the full clean-environment procedure, see [`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md).

---

## Evidence and reproducibility

Every advanced run persists evidence under:

```text
artifacts/runs/<run_id>/
```

Aggregate benchmark outputs are written to:

```text
artifacts/eval/advanced_iteration_5_benchmark_v2/
  summary.json
  cases.jsonl
  cases.partial.jsonl
  report.md
```

Development trajectories are preserved under [`traces/`](traces/). They capture human instructions, observable tool actions, retries, failures, checkpoints, and measured results without reconstructing private chain-of-thought.

The final Iteration 5 verification transcript is preserved at:

```text
traces/trace-016-iteration-5/verification.txt
```

---

## Scope and safety boundary

The current MVP is intentionally narrow.

### Supported

- Python benchmark cases;
- pytest-based local execution;
- issue descriptions supplied as public text;
- original and patched code supplied as controlled fixture directories;
- deterministic public-test execution;
- a deliberately small public-contract vocabulary for deterministic probe compilation;
- local Ollama or an OpenAI-compatible provider abstraction;
- evidence-backed five-way verdicts.

### Not claimed

- arbitrary GitHub repository verification;
- arbitrary programming-language support;
- formal correctness proofs;
- unrestricted execution of untrusted repositories;
- authoritative security review;
- automatic merging or deployment of patches;
- universal 100% patch-verification accuracy.

For the hackathon MVP, execution is limited to bundled/synthetic controlled repositories with explicit timeouts and no autonomous repository-changing actions.

---

## Project structure

```text
src/refute/
  agents/                  agent roles + deterministic probe components
  benchmark/               evaluation and oracle-loading code
  cli.py                   command-line interface
  executor.py              deterministic command execution
  evidence.py              persisted evidence records
  orchestrator.py          verification run state machine
  verify_v5.py             frozen Iteration 5 verifier

benchmark/                 original controlled benchmark fixtures
benchmark_v2/              generated oracle-free public cases
eval/benchmark_v2/         evaluator-only oracles + hidden checks
scripts/                   benchmark build and integrity audit
tests/                     unit and regression tests
traces/                    normalized development trajectories
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
| [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md) | measured experiments, regressions, and design decisions |
| [`TRAJECTORIES.md`](TRAJECTORIES.md) | human-readable index of coding-agent trajectories |
| [`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md) | exact clean-environment reproduction procedure |
| [`traces/`](traces/) | normalized per-iteration execution and development evidence |

---

## Design principle

> **The breakthrough was not a better prompt. It was giving the model less responsibility.**

`refute` uses the language model where semantic prioritization is useful, deterministic code where truth is mechanically observable, and evidence as the boundary between the two.

---

## License

MIT
