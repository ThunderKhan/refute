# Improvement Changelog

This file records `refute` experiments as measured engineering changes rather than a feature list. Unless stated otherwise, benchmark comparisons use the same ten controlled cases and local Ollama model `qwen3:0.6b` at temperature 0.

## Baseline v1 — static issue + diff review

Hypothesis: a single general-purpose LLM can classify bug-fix patches from issue text and a static diff.

Result:
- verdict accuracy: **10.0%**
- false acceptance rate: **57.1%**
- average runtime: **2.405s/case**

Decision: freeze as Baseline v1. Do not tune after seeing advanced results.

## Advanced Iteration 1 — Investigator + deterministic existing-test execution

Hypothesis: structured issue interpretation plus deterministic runtime evidence will improve verdict quality and reduce unsafe approvals.

Result:
- verdict accuracy: **40.0%**
- false acceptance rate: **28.6%**
- average runtime: **5.641s/case**

Decision: keep Investigator + deterministic runtime evidence.

## Advanced Iteration 2 — generated reproduction + bounded retry

Hypothesis: an agent/tool feedback loop that generates and executes reported-bug reproductions will improve on Iteration 1.

Result:
- verdict accuracy: **10.0%**
- false acceptance rate: **0.0%**
- average runtime: **36.569s/case**

Observed failure: generated tests that failed on both original and patched implementations were incorrectly treated as successful reproductions.

Decision: do not keep Iteration 2 semantics as the final design. Preserve it as a negative experiment.

## Advanced Iteration 2.1 — discriminating reproduction semantics

Hypothesis: only accepting original-FAIL/patch-PASS generated tests as successful reproductions will recover accuracy while retaining safer approval behavior.

Result:
- verdict accuracy: **40.0%**
- false acceptance rate: **0.0%**
- average runtime: **52.584s/case**

Decision: keep discriminating semantics, but weight evidence and reduce wasted retries.

## Advanced Iteration 2.2 — evidence weighting + stagnation stop

Result:
- verdict accuracy: **30.0%**
- false acceptance rate: **0.0%**
- average runtime: **50.863s/case**

Decision: move deterministic suite analysis earlier.

## Advanced Iteration 2.3 — deterministic test-delta engine + conditional reproduction

Result:
- completed cases: **9/10**
- errors: **1** (`case_007` Investigator timeout)
- verdict accuracy: **50.0%**
- false acceptance rate: **0.0%**
- average runtime: **11.657s/case**

Decision: keep the test-delta engine, but move deterministic execution ahead of the Investigator.

## Advanced Iteration 2.4 — test-first routing

Benchmark v1 result:
- completed cases: **10/10**
- errors: **0**
- verdict accuracy: **100.0%**
- false acceptance rate: **0.0%**
- average runtime: **1.019s/case**

Interpretation: this is not a valid final agentic improvement result because every case was solved without agent calls. Benchmark v1 exposed too much oracle information through public tests.

Decision: preserve 2.4 as a systems-engineering and benchmark-diagnostic result, but do not use its 100.0% as the final hackathon agentic claim.

## Benchmark v2 — oracle separation

Public cases use `case.json` with no expected verdict. Evaluator-only verdicts and hidden tests live under `eval/benchmark_v2/`; the loader rejects inline oracle leakage and reports use separate artifact directories.

Local verification:
- `python -m pytest`: **48 passed in 31.98s**;
- builder produced **10** public cases;
- separation audit: **PASSED**;
- `case_002` publicly shows original FAIL / patch PASS while its broader oracle remains withheld.

### Frozen Baseline v2

- verdict accuracy: **10.0%**
- false acceptance rate: **57.1%**
- average runtime: **2.527s/case**

Decision: freeze this first clean Baseline v2 result.

### Frozen Iteration 2.4 ablation on Benchmark v2

- completed cases: **10/10**
- errors: **0**
- verdict accuracy: **60.0%**
- false acceptance rate: **57.1%**
- average runtime: **0.929s/case**

Four false `complete_fix` verdicts remained:
- `case_002`: upper-boundary failure;
- `case_003`: internal-space regression;
- `case_006`: tiny-limit failure;
- `case_007`: invalid-operand regression.

Interpretation: the drop from 100.0% on Benchmark v1 to 60.0% on Benchmark v2 confirms the previous saturation came from public-test leakage. These four misses define the missing capability: active falsification beyond the reported trigger.

## Advanced Iteration 3 — Challenger

Hypothesis: after a public reported-trigger test changes from FAIL on original to PASS on patch, an agent that actively proposes nearby issue-grounded falsification cases can recover hidden partial fixes and regressions without seeing evaluator-only hidden tests or verdicts.

Implemented workflow:
- deterministic public original/patched tests still run first;
- mechanically decisive partial/ineffective/regression outcomes retain the Iteration 2.4 fast path;
- only a `suite_repaired` public delta enters the agentic challenge path;
- Investigator summarizes expected behavior and risk areas from public issue + diff;
- Challenger generates **1–3** nearby pytest cases focused on boundaries, preserved invariants, small-limit behavior, and exception specificity;
- generated tests use the existing conservative safety validator and cannot use network/shell/destructive operations;
- every challenge runs on both original and patch;
- original PASS + patch FAIL is executable regression evidence;
- original FAIL + patch FAIL after the public trigger was repaired is executable remaining-bug evidence and maps to `partial_fix`;
- invalid pytest execution (timeout or exit code 2+) is never treated as semantic counterexample evidence;
- if all valid Challenger cases pass on the patch, the bounded search returns `complete_fix`; if no valid decisive challenge exists, it remains `inconclusive`;
- oracle and hidden-test files are never loaded by `verify_case_v3`.

New evaluation metrics:
- challenged cases;
- challenge candidates executed;
- challenge counterexamples;
- Challenger case yield = challenged cases with at least one executable counterexample / challenged cases.

Target against frozen Benchmark v2 Iteration 2.4:
- accuracy **> 60.0%**;
- false acceptance rate **< 57.1%**;
- useful counterexamples on the deliberately hidden nearby-failure cases.

Status: **implementation complete; local pytest, targeted cases, and Benchmark v2 run pending.** Do not claim an Iteration 3 improvement until the local measurement is supplied.
