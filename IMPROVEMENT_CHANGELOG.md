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

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **40.0%**
- FAR: **0.0%**
- Challenger case yield: **42.9%**
- executable counterexamples: **5**
- average runtime: **14.774s/case**

Interpretation: Iteration 3 achieved the safety goal, but true complete fixes were vulnerable to poorly grounded fail/fail challenges and runtime rose sharply.

Decision: preserve Iteration 3 as a safety-positive / accuracy-negative experiment.

## Advanced Iteration 3.1 — exact-quote grounded Challenger

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- average runtime: **20.438s/case**

Interpretation: exact quote copying was too brittle for `qwen3:0.6b`; the stricter grounding interface reduced fabrication but collapsed useful generation.

Decision: preserve 3.1 as a negative experiment.

## Advanced Iteration 3.2 — deterministic contract IDs

Hypothesis: extract issue-contract spans deterministically, assign stable IDs, and ask Challenger to select an ID instead of reproducing a free-form quote.

Local verification:
- `python -m pytest`: **60 passed in 47.71s**;
- targeted case_001, case_002, and case_003 produced two executable candidates with zero generation failures, but all were `non_decisive`;
- targeted case_006 produced one `non_decisive` candidate and one generation failure;
- targeted case_007 produced one `invalid_execution` candidate and one generation failure;
- all five targeted suite-repaired cases remained `inconclusive`.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- challenge generation failures: **9**
- average runtime: **25.966s/case**

Interpretation:
- deterministic contract IDs improved the interface relative to exact quote copying on several targeted runs, but did not recover useful counterexamples;
- the dominant failure shifted from pure generation rejection to **semantic qualification**: generated tests often executed but were `non_decisive` because the model-selected evidence kind did not justify treating fail/fail as a remaining requirement;
- batch generation remained unstable and latency worsened;
- simply making grounding references easier is insufficient. An executable failing test still needs independent validation that its assertion is actually entailed by the selected public contract.

Decision: preserve 3.2 as another measured negative experiment. Keep deterministic contract extraction, but separate **test proposal** from **evidence qualification**.

## Advanced Iteration 3.3 — contract-entailment critic

Hypothesis: retain 3.2's deterministic contract IDs, but require every executable patch-failing challenge to pass a second, strict contract-entailment critic before it can influence the verdict.

Changes:
- Challenger still proposes a single contract-ID-grounded pytest test;
- deterministic execution first categorizes the observed shape as survived, regression candidate, remaining-failure candidate, invalid, or non-decisive;
- only patch-failing candidates are sent to a separate Critic agent;
- the Critic receives only the selected public contract span and generated test, and returns `supported: true|false` with a short reason;
- a regression candidate becomes `regression_counterexample` only if the Critic confirms the assertion is directly supported by the public contract;
- a fail/fail candidate becomes `remaining_requirement_counterexample` only when both the Challenger declares `remaining_requirement` and the Critic confirms direct contract support;
- unsupported executable failures feed back into the bounded Challenger retry instead of becoming verdict evidence;
- patch-passing challenges do not pay for the Critic call;
- oracle and hidden tests remain unavailable to both Challenger and Critic.

Target: recover useful counterexamples without reintroducing Iteration 3's fabricated-failure false negatives. Status: implementation complete; local verification pending.
