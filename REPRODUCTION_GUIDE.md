# Reproduction Guide

This guide reproduces the frozen `refute` Benchmark v2 result for Advanced Iteration 5 and separately validates the current product surfaces added afterward: the dashboard, public-GitHub-PR workflow, and MCP server.

## Environment

Reference configuration:

- Windows PowerShell
- Python 3.11+
- local Ollama provider
- model: `qwen3:0.6b`
- benchmark: oracle-separated Benchmark v2

The core verifier has no mandatory runtime Python dependencies. `pytest` and the MCP SDK are installed through development/optional extras. The frontend uses Node/npm separately.

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

If the Ollama desktop/service is not already running, start it before evaluation or live verification.

## 3. Build and audit Benchmark v2

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

Frozen Iteration 5 measurement-point verification on 2026-08-30:

```text
72 passed in 63.16s
```

After the dashboard, real-PR, and MCP integrations were added, the project suite was later locally verified as:

```text
92 passed in 67.48s
```

The 92-test result validates the later product code; it does **not** replace or retroactively change the frozen Iteration 5 benchmark measurement.

## 5. Optional: inspect one public benchmark case

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

## 8. Inspect generated benchmark evidence

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

The frozen human-supplied Iteration 5 verification transcript is preserved at:

```text
traces/trace-016-iteration-5/verification.txt
```

## 9. Run the local dashboard

Install/build the frontend:

```powershell
cd frontend
npm install
npm run build
cd ..
```

Start the Python dashboard API in one terminal:

```powershell
python -m refute.dashboard_server
```

Start Vite in another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173/verify`.

Two verification modes are available:

- **Benchmark**: reproducible controlled cases such as `case_002`.
- **GitHub PR**: a public Python/pytest PR. The user must explicitly acknowledge that refute will provision dependencies and execute target-repository tests locally.

The GitHub mode is not part of the frozen 10-case benchmark metric.

## 10. Validate the public-GitHub-PR path

A compatible PR can be pasted into the dashboard. When the PR changes pytest files, refute can reuse those patch-authored tests as a deterministic reproduction against base and patch. If the normal public-contract compiler cannot produce independent probes, a bounded nearby-test adversary can prioritize existing tests while deterministic execution decides whether they survive or reveal a regression.

A real-repository run may validly end as `inconclusive` even after the reported trigger is repaired. Passing a few nearby tests is confidence evidence, not proof of completeness.

### Safety boundary

The current implementation creates an isolated per-run Python environment but does **not** provide strong OS/container sandboxing. Installing dependencies and running tests executes third-party code locally. Use only repositories you are willing to execute and keep the explicit human approval gate enabled.

## 11. Validate MCP integration

The local stdio MCP server is optional:

```powershell
python -m refute.mcp_server
```

For MCP Inspector development:

```powershell
mcp dev src/refute/mcp_server.py
```

The Inspector launcher may require `uv` as development tooling:

```powershell
python -m pip install uv
```

The proven MCP flow is:

```text
inspect_pr(url)
verify_pr(url, confirm_execution=true) -> job_id
get_verify_job(job_id) -> poll until complete
get_run(run_id) -> persisted result without re-execution
```

`verify_pr` is asynchronous so long dependency/test runs do not depend on one MCP request staying open. See [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md) for host configuration.

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

## Final clean-clone checklist

Before submission, perform one final run from a newly cloned directory and record:

```text
Git commit SHA
Python version
Ollama version
model name
benchmark audit result
pytest result
frontend npm build result
one benchmark verification result
one public-PR inspect/verification result
MCP inspect -> async verify -> persisted get_run result
```

Do not claim this final clean-clone pass until it has actually been executed.

## Troubleshooting

If Ollama returns a connection-refused error, confirm the Ollama application/service is running. `ollama list` should show `qwen3:0.6b` before evaluation.

If generated Benchmark v2 cases are missing, rerun:

```powershell
python scripts/build_benchmark_v2.py
```

If MCP Inspector reports that `uv` is not recognized, install `uv` as development tooling or test the stdio server directly through the Python executable used by the host.

If you are comparing results after changing verification code or prompts, do not overwrite the frozen Iteration 5 claim. Treat the modified configuration as a new experiment and record it separately.
