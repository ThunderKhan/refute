# Reproduction Guide

This guide reproduces the frozen `refute` Benchmark v2 result for Advanced Iteration 5.

## Environment

Tested configuration:

- Windows PowerShell
- Python 3.11+
- local Ollama provider
- model: `qwen3:0.6b`
- benchmark: oracle-separated Benchmark v2

The project itself has no runtime Python dependencies. `pytest` is installed through the `dev` extra for tests and benchmark cases.

## 1. Clone and install

```powershell
git clone https://github.com/ThunderKhan/refute.git
cd refute
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## 2. Prepare the local model

Install/launch Ollama separately, then make sure the model exists locally:

```powershell
ollama pull qwen3:0.6b
ollama list
```

If the Ollama desktop/service is not already running, start it before evaluation.

## 3. Build and audit Benchmark v2

Benchmark v2 public cases are generated from the controlled legacy benchmark while withholding evaluator-only verdicts and hidden tests.

```powershell
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
```

The audit should finish with:

```text
AUDIT PASSED: public cases are oracle-free and hidden behavior is separated as designed.
```

## 4. Run the project test suite

```powershell
python -m pytest
```

Frozen local verification on 2026-08-30:

```text
72 passed in 63.16s
```

Exact wall-clock time can vary by machine.

## 5. Optional: inspect one public case

```powershell
refute inspect benchmark_v2\case_002
```

The important integrity signal is:

```text
expected verdict: withheld from public case
```

## 6. Reproduce the static Baseline v2

```powershell
refute eval-baseline benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --llm-timeout 30
```

Frozen Baseline v2 result:

- verdict accuracy: **10.0%**
- false acceptance rate: **57.1%**
- average runtime: **2.527s/case**

## 7. Reproduce Advanced Iteration 5

```powershell
refute eval-advanced benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

Frozen clean result:

```text
mode: advanced iteration 5 benchmark v2
model: qwen3:0.6b
cases: 10
oracle separated: yes
completed cases: 10
errors: 0
verdict accuracy: 100.0%
false acceptance rate: 0.0%
challenger case yield: 57.1%
challenge counterexamples: 4
challenge generation failures: 0
probe planner fallback cases: 0
average runtime: 5.077s
```

Expected per-case verdicts:

| Case | Verdict |
|---|---|
| case_001 | `complete_fix` |
| case_002 | `partial_fix` |
| case_003 | `regression_introduced` |
| case_004 | `ineffective_fix` |
| case_005 | `complete_fix` |
| case_006 | `partial_fix` |
| case_007 | `regression_introduced` |
| case_008 | `ineffective_fix` |
| case_009 | `complete_fix` |
| case_010 | `inconclusive` |

Wall-clock runtime may vary. Verdicts are the primary reproducibility target.

## 8. Inspect generated evidence

Per-run evidence is written under:

```text
artifacts/runs/<run_id>/
```

The aggregate Iteration 5 benchmark report is written under:

```text
artifacts/eval/advanced_iteration_5_benchmark_v2/
  summary.json
  cases.jsonl
  cases.partial.jsonl
  report.md
```

The frozen human-supplied verification transcript is preserved at:

```text
traces/trace-016-iteration-5/verification.txt
```

## Benchmark separation rule

The verification path may inspect only public case material such as:

```text
benchmark_v2/case_XXX/case.json
benchmark_v2/case_XXX/issue.md
benchmark_v2/case_XXX/original/
benchmark_v2/case_XXX/patched/
```

Evaluator-only material lives at:

```text
eval/benchmark_v2/oracles.json
eval/benchmark_v2/hidden_tests.json
```

Those files are used to score already-produced verdicts. They are not inputs to Iteration 5's contract compiler, probe planner, or verifier.

## What Iteration 5 is actually measuring

Iteration 5 is not a general theorem prover or universal patch verifier. It measures a narrower hypothesis:

> When public issue contracts contain mechanically recognizable requirements, move those requirements into deterministic probe construction and use the agent only for bounded prioritization.

The benchmark deliberately includes complete fixes, partial fixes, ineffective patches, regressions, and one case where the available evidence is insufficient. The system is rewarded for returning `inconclusive` rather than fabricating certainty in that last case.

## Troubleshooting

If Ollama returns a connection-refused error, confirm the Ollama application/service is running. `ollama list` should show `qwen3:0.6b` before evaluation.

If generated Benchmark v2 cases are missing, rerun:

```powershell
python scripts/build_benchmark_v2.py
```

If you are comparing results after changing code or prompts, do not overwrite the frozen Iteration 5 claim. Treat the modified configuration as a new experiment and record it separately.
