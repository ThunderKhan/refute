# Final Submission Checklist

This file is the pre-submission gate for `refute`. Do not mark an item complete unless it has actually been observed.

## 1. Freeze the measured claim

- [x] Primary metric is verdict accuracy on controlled Benchmark v2.
- [x] Baseline v2 is frozen at **10.0% accuracy / 57.1% FAR / 2.527s per case**.
- [x] Advanced Iteration 5 is frozen at **100.0% accuracy / 0.0% FAR / 5.077s per case** on the same ten oracle-separated cases.
- [x] README explicitly says this is **not** a universal patch-verification accuracy claim.
- [x] Benchmark v1's invalid 100% saturation is preserved as a negative benchmark-design experiment.

## 2. Benchmark integrity

Run from a clean clone:

```powershell
python scripts/build_benchmark_v2.py
python scripts/audit_benchmark_v2.py
```

- [x] Audit ends with `AUDIT PASSED`.
- [x] Public cases are confirmed oracle-free by the benchmark audit.
- [x] `oracles.json` and `hidden_tests.json` remain evaluator-only according to the benchmark audit.

Clean-clone verification on 2026-08-30:

```text
built 10 public cases under benchmark_v2
AUDIT PASSED: public cases are oracle-free and hidden behavior is separated as designed.
```

## 3. Current project tests

```powershell
python -m pytest
```

- [x] Current clean-clone suite passes.
- [x] Exact clean-clone checkpoint recorded: **92 passed in 73.36s**.

Historical checkpoints remain labelled separately:

- Frozen Iteration 5 measurement point: `72 passed in 63.16s`.
- Earlier product/MCP integration checkpoint: `92 passed in 67.48s`.
- Final clean-clone pre-submission checkpoint: `92 passed in 73.36s`.

## 4. Benchmark reproduction

```powershell
refute eval-baseline benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --llm-timeout 30
refute eval-advanced benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

- [ ] Baseline completes all 10 cases.
- [ ] Advanced completes all 10 cases.
- [ ] Per-case advanced verdicts match `REPRODUCTION_GUIDE.md`.
- [ ] Do not silently replace frozen metrics if wall-clock timing changes.

## 5. Dashboard build and live verification

```powershell
cd frontend
npm install
npm run build
```

- [x] Production frontend build succeeds in a clean clone.
- [x] `/verify` opens without hard-refresh routing issues.
- [x] Benchmark `case_002` demonstrates `partial_fix` with an upper-boundary counterexample.
- [x] Public GitHub PR inspection renders Markdown and task-list checkboxes correctly.
- [x] Real-PR run shows targeted reproduction, nearby-test evidence when needed, and conservative `inconclusive` behavior when completeness evidence is insufficient.

Clean-clone frontend checkpoint on 2026-08-30:

```text
vite v8.2.2
1828 modules transformed
production build succeeded in 11.55s
```

## 6. MCP integration

- [x] `inspect_pr` proven through MCP Inspector.
- [x] `verify_pr` returns an async `job_id` rather than timing out.
- [x] `get_verify_job` proven through `running` to `complete`.
- [x] `get_run` proven to reload persisted evidence without re-execution.
- [x] Explicit `confirm_execution=true` gate remains required before third-party code execution.

Before submission, verify the current clean clone still imports the MCP server:

```powershell
python -c "from refute.mcp_server import mcp; print('refute MCP import OK')"
```

- [x] Import succeeds in the clean-clone checkpoint.

## 7. Safety / claim boundary

- [x] GitHub mode is described as compatible **public Python/pytest PRs**, not universal repository support.
- [x] Dependency installation and pytest execution require human acknowledgement.
- [x] Docs state that the per-run Python environment is **not** strong OS/container sandboxing.
- [x] No automatic merge/deploy action exists.
- [x] `inconclusive` is treated as a valid result.

## 8. Trace / trajectory evidence

- [x] `TRAJECTORIES.md` indexes Iterations 1 through 5 and the negative/removed experiments.
- [x] `traces/README.md` indexes all sixteen substantial engineering rounds.
- [x] Final `trace-016-iteration-5/` contains human checkpoint, metadata, normalized actions, summary, and frozen verification transcript.
- [x] Trace policy forbids reconstructing hidden chain-of-thought or fabricating missing raw events.

## 9. Final environment record

Clean-clone checkpoint observed on 2026-08-30:

```text
clone SHA: 653ae58f464b9a6b6457a1a2b0e050eb2abee355
Python 3.12.10
Ollama 0.33.0
qwen3:0.6b present (522 MB)
Node v24.14.1
npm 11.11.0
```

Because documentation commits were pushed after this clone, rerun the following immediately before submission and record the then-current SHA:

```powershell
git rev-parse HEAD
python --version
ollama --version
ollama list
node --version
npm --version
```

- [ ] Final post-hardening Git SHA recorded.
- [x] Python version recorded for the clean-clone checkpoint.
- [x] Ollama version and `qwen3:0.6b` presence recorded for the clean-clone checkpoint.
- [x] Node/npm versions recorded for dashboard reproduction.

## 10. Demo video <= 5 minutes

Suggested structure:

```text
0:00  Problem: patches can look correct without being complete
0:25  Baseline failure / false acceptance problem
0:50  Dashboard: paste PR / controlled case
1:20  case_002: public test repairs lower boundary
1:45  refute derives upper-boundary probe and falsifies patch
2:15  Real GitHub PR: targeted base-vs-patch reproduction
2:55  Nearby-test adversary + conservative inconclusive result
3:25  Architecture: agents prioritize, deterministic tools observe
3:55  Experiment journey: prompt-heavy plateau -> responsibility reduction
4:25  Metrics: 10% -> 100%, FAR 57.1% -> 0% on Benchmark v2
4:40  Reproducibility + MCP integration + limits
4:55  Hot take / close
```

- [ ] Video length <= 5 minutes.
- [ ] Every metric shown is labelled Benchmark v2.
- [ ] Real GitHub PR is clearly presented as product demonstration, not benchmark evidence.
- [ ] Safety acknowledgement is visible or mentioned.

## 11. Submission package

- [x] Public GitHub repository.
- [x] README with problem, architecture, metrics, scope, dashboard, and MCP.
- [x] Improvement Changelog.
- [x] Reproduction Guide.
- [x] Agent trajectories / normalized trace archive.
- [ ] Final demo video link.
- [ ] Final submission description.
- [ ] Final representative screenshots selected.

## Stop condition

The clean-clone install/audit/tests/frontend-build/MCP-import gate has passed. Do not add new verification semantics unless a submission-blocking defect is found. Prefer documentation, evidence, and demo reliability over new features.
