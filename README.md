# refute

> A patch should not be trusted because it looks correct. It should survive attempts to falsify it.

`refute` is an evidence-backed agentic workflow for checking whether a software patch actually fixes a reported bug, only fixes the obvious example, does nothing, or introduces a regression.

Instead of asking one language model to read a diff and guess, `refute` combines deterministic execution with a deliberately narrow agent role. Public tests establish what changed mechanically. When the reported trigger appears repaired, a deterministic contract compiler derives nearby probes from the public issue contract. A local model prioritizes those probes, deterministic pytest execution runs them on the original and patched code, and the final verdict is constrained by the resulting evidence.

## Why this exists

Patch review has an uncomfortable failure mode: a change can look plausible, satisfy the reported example, and still be incomplete or harmful nearby.

Examples include:
- fixing the lower boundary while leaving the upper boundary broken;
- trimming whitespace by accidentally deleting meaningful internal spaces;
- handling division by zero by swallowing unrelated type errors;
- satisfying one truncation example while violating the length invariant at tiny limits.

`refute` is built around falsification rather than plausibility.

## Verdicts

`refute` returns one of five verdicts:

- `complete_fix`
- `partial_fix`
- `ineffective_fix`
- `regression_introduced`
- `inconclusive`

`inconclusive` is intentional. When the available evidence cannot justify a stronger claim, the system prefers uncertainty to fabrication.

## Final workflow

```text
issue + original + patch
        |
        v
run public tests on original and patch
        |
        v
compare deterministic test delta
        |
        +-- mechanically decisive? --> verdict
        |
        v
suite appears repaired
        |
        v
deterministic public-contract probe compiler
        |
        v
bounded probe pool
        |
        v
agent prioritizes probe IDs
        |
        v
deterministic pytest execution
  on original + patched code
        |
        v
evidence-constrained verdict
```

The governing invariant is:

> **Agents prioritize and reason. Deterministic tools observe. Evidence constrains the verdict.**

## Measured improvement

The final evaluation uses **Benchmark v2**, a ten-case controlled synthetic benchmark where public cases contain no expected verdict and evaluator-only oracles/hidden tests are stored separately.

All measurements below use local Ollama with `qwen3:0.6b` at temperature 0.

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

Iteration 5 completed all ten cases with:

- **10/10 correct verdicts**
- **0 errors**
- **4 executable nearby counterexamples**
- **57.1% Challenger case yield**
- **0 challenge-generation failures**
- **0 planner fallbacks**

The four nearby failures recovered by the advanced workflow were an inclusive upper boundary, internal-space preservation, tiny truncation limits, and exception specificity.

## What changed across iterations

The main result was not produced by increasingly elaborate prompting.

Early advanced iterations asked the model to generate pytest source, then added grounding, contract IDs, and a second critic. Those systems became safer but remained unreliable and slow. Iteration 4 removed Python generation but still asked the model to invent semantic assertions.

Iteration 5 changed the responsibility boundary: mechanically derivable test semantics moved into a deterministic public-contract compiler, while the model was reduced to prioritizing a bounded set of probe IDs. That structural change produced the first clean 10/10 Benchmark v2 run.

See [`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md) for the measured experiment history and [`TRAJECTORIES.md`](TRAJECTORIES.md) for normalized coding-agent trajectories.

## Benchmark integrity

Benchmark v1 accidentally exposed enough behavior through public tests that the deterministic 2.4 workflow reached 100% without using an agent. That result was treated as a benchmark failure rather than a success.

Benchmark v2 fixes the leakage:

```text
benchmark_v2/case_XXX/
  case.json        # public metadata, no expected verdict
  issue.md
  original/
  patched/

eval/benchmark_v2/
  oracles.json     # evaluator-only
  hidden_tests.json
```

The verification path does **not** load the evaluator oracle or hidden-test files. They are used only after a case verdict has been produced, to score the benchmark.

## Quick start

Requirements:

- Python 3.11+
- Ollama
- `qwen3:0.6b`

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ollama pull qwen3:0.6b
python scripts/build_benchmark_v2.py
python -m pytest
refute eval-advanced benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

For a step-by-step reproduction procedure and expected artifact paths, see [`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md).

## Evidence and trajectories

Each verification run writes evidence under:

```text
artifacts/runs/<run_id>/
```

Aggregate benchmark artifacts are written under:

```text
artifacts/eval/advanced_iteration_5_benchmark_v2/
```

Representative development trajectories are preserved under `traces/`. They record human instructions, observable tool actions, failures, retries, verification results, and checkpoints without exposing private chain-of-thought.

## Scope and limitations

The final 100.0% result is **only a result on the ten-case controlled Benchmark v2**. It is not a claim that `refute` verifies arbitrary repositories or patches with 100% accuracy.

The current MVP intentionally supports:

- Python benchmark cases;
- pytest-based deterministic execution;
- a small public-contract vocabulary used by the deterministic probe compiler;
- local Ollama or a generic OpenAI-compatible provider through the existing provider abstraction.

It does not claim formal correctness, unrestricted repository execution, arbitrary-language support, or production auto-merge safety.

## Repository map

```text
src/refute/                    core package
src/refute/agents/             agent and deterministic probe components
src/refute/benchmark/          evaluators and oracle loader
benchmark/                     legacy controlled cases
benchmark_v2/                  generated oracle-free public cases
eval/benchmark_v2/             evaluator-only oracle + hidden behavior
scripts/                       benchmark build/audit utilities
tests/                         regression/unit tests
traces/                        normalized development trajectories
```

## License

MIT
