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
- true complete fixes were vulnerable to poorly grounded fail/fail challenge tests;
- several suite-repaired cases produced no usable challenge candidate or timed close to the provider limit.

Decision: preserve Iteration 3 as a measured safety-positive / accuracy-negative experiment.

## Advanced Iteration 3.1 — exact-quote grounded Challenger

Hypothesis: requiring an exact issue quote and one candidate per call will reduce fabricated counterexamples while retaining safety.

Local verification:
- `python -m pytest`: **56 passed in 43.99s**;
- all five targeted suite-repaired cases invoked Challenger;
- case_001, case_003, case_006, and case_007 produced **two generation failures and zero executable candidates**;
- case_002 produced one executable candidate, but it was `invalid_execution` after one generation failure.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- average runtime: **20.438s/case**

Interpretation:
- the grounding gate was too brittle for `qwen3:0.6b`; asking the model to reproduce a free-form exact quote caused generation rejection on nearly every suite-repaired case;
- the system stayed safe by returning `inconclusive`, but capability collapsed and runtime increased because it paid for repeated failed structured generations;
- exact grounding is valuable, but the model should select from deterministic issue spans rather than reproduce the span text itself.

Decision: preserve 3.1 as a negative experiment demonstrating that stricter grounding can reduce fabrication while simultaneously destroying generation reliability if the grounding interface is model-hostile.

## Advanced Iteration 3.2 — deterministic contract IDs

Hypothesis: extract issue-contract spans deterministically, assign stable IDs (`c1`, `c2`, ...), and ask the Challenger to select a contract ID rather than copy an exact quote. This should keep grounding auditable while reducing structured-output failure and latency.

Changes:
- deterministic issue text is split into numbered contract spans before the model call;
- Challenger returns `contract_id`, `kind`, `rationale`, and one pytest test;
- the grounding gate validates the selected ID mechanically; no free-form quote matching is required;
- the Challenger prompt directly includes the allowed contract IDs and corresponding issue text;
- Iteration 3.2 removes the separate Investigator call from the suite-repaired challenge path, reducing both latency and provider failure surface;
- one candidate is generated per call with at most two attempts;
- execution semantics remain conservative: original PASS + patch FAIL => regression evidence; original FAIL + patch FAIL counts only for a `remaining_requirement`; invalid pytest execution is not evidence;
- oracle and hidden tests remain unavailable to the verification path.

Target: materially reduce 3.1 generation failures while recovering useful counterexamples and keeping FAR below Iteration 2.4's 57.1%. Status: implementation complete; local verification pending.
