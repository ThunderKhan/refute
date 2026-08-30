# Improvement Changelog

This file records `refute` experiments as measured engineering changes rather than a feature list. Unless stated otherwise, benchmark comparisons use the same ten controlled cases and local Ollama model `qwen3:0.6b` at temperature 0.

## Baseline v1 — static issue + diff review

Result: 10.0% accuracy, 57.1% FAR, 2.405s/case. Frozen.

## Advanced Iteration 1

Result: 40.0% accuracy, 28.6% FAR, 5.641s/case.

## Advanced Iteration 2

Result: 10.0% accuracy, 0.0% FAR, 36.569s/case. Negative experiment: fail/fail generated tests were treated too strongly.

## Advanced Iteration 2.1

Result: 40.0% accuracy, 0.0% FAR, 52.584s/case. Kept discriminating reproduction semantics.

## Advanced Iteration 2.2

Result: 30.0% accuracy, 0.0% FAR, 50.863s/case. Evidence weighting improved safety but not accuracy/runtime.

## Advanced Iteration 2.3

Result: 50.0% accuracy, 0.0% FAR, 11.657s/case with 9/10 completed. Deterministic test deltas substantially reduced cost, but the Investigator still blocked one case.

## Advanced Iteration 2.4 — test-first routing

Benchmark v1: 100.0% accuracy, 0.0% FAR, 1.019s/case. This was diagnosed as benchmark saturation because every case was solved without agent calls.

## Benchmark v2 — oracle separation

Public cases use `case.json` with no expected verdict. Evaluator-only verdicts and hidden tests live under `eval/benchmark_v2/`; the loader rejects inline oracle leakage.

Local verification: 48 tests passed, builder produced 10 public cases, separation audit passed.

### Frozen Baseline v2

- accuracy: **10.0%**
- FAR: **57.1%**
- runtime: **2.527s/case**

### Frozen Iteration 2.4 on Benchmark v2

- accuracy: **60.0%**
- FAR: **57.1%**
- runtime: **0.929s/case**

The four false `complete_fix` verdicts were case_002, case_003, case_006, and case_007. This confirmed that Benchmark v1's apparent perfection came from public-test leakage.

## Advanced Iteration 3 — Challenger

Hypothesis: Challenger-generated nearby tests can recover hidden partial fixes and regressions after the public trigger appears repaired.

Clean local verification:
- `python -m pytest`: **53 passed in 37.42s**;
- case_002 targeted run: Challenger found one `remaining_bug_counterexample` and correctly returned `partial_fix`;
- case_003 targeted run: Challenger found a counterexample but classified it as remaining-bug evidence, returning `partial_fix` instead of the regression oracle;
- case_001 targeted run: no usable challenge candidate, so the system returned `inconclusive` rather than fabricate completeness.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **40.0%**
- FAR: **0.0%**
- Challenger case yield: **42.9%**
- executable counterexamples: **5**
- average runtime: **14.774s/case**

Interpretation:
- Iteration 3 achieved the safety goal: false acceptance fell from 57.1% to 0.0%;
- however, accuracy fell from 60.0% to 40.0% and latency rose sharply;
- true complete fixes (`case_001`, `case_005`, `case_009`) were vulnerable to poorly grounded fail/fail challenge tests, creating false negative/partial verdicts;
- several suite-repaired cases produced no usable challenge candidate or timed close to the provider limit;
- a fail/fail generated test is not automatically trustworthy evidence of a remaining requirement merely because it executes cleanly.

Decision: preserve Iteration 3 as a measured safety-positive / accuracy-negative experiment. Do not discard the Challenger; strengthen candidate grounding and generation reliability before another benchmark run.

## Advanced Iteration 3.1 — grounded single-candidate Challenger

Hypothesis: requiring each challenge to cite an exact issue-report phrase, generating one focused candidate at a time, and using bounded retry will reduce fabricated counterexamples while retaining the FAR improvement from Iteration 3.

Changes:
- Challenger returns exactly one candidate per call rather than a 1–3 test bundle;
- every candidate declares `remaining_requirement` or `regression_guard`;
- every candidate must include a `grounding_quote` copied from the issue report;
- a deterministic quote gate rejects invented/non-issue grounding before execution;
- pytest exit codes other than 0/1 and timeouts remain invalid evidence;
- original PASS + patch FAIL remains high-confidence regression evidence;
- original FAIL + patch FAIL counts as partial-fix evidence only for an explicitly grounded `remaining_requirement` candidate;
- non-decisive/survived/invalid attempts can feed one bounded retry;
- if all valid grounded attempts survive, bounded evidence may support `complete_fix`; unusable evidence remains `inconclusive`;
- oracle and hidden tests remain unavailable to the agentic path.

Target: recover accuracy above Iteration 3 while retaining materially lower FAR than Iteration 2.4. Status: implementation complete; local verification pending.
