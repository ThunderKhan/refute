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

Local verification:
- `python -m pytest`: **60 passed in 47.71s**;
- targeted case_001, case_002, and case_003 produced executable candidates but no qualified counterexamples;
- targeted case_006 and case_007 still showed generation/invalid-execution failures.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- challenge generation failures: **9**
- average runtime: **25.966s/case**

Interpretation: deterministic contract IDs improved grounding ergonomics but did not solve semantic evidence qualification. Generated tests could execute while still failing to justify a negative verdict.

Decision: preserve 3.2 as a negative experiment. Separate test proposal from evidence qualification.

## Advanced Iteration 3.3 — contract-entailment critic

Hypothesis: require patch-failing generated challenges to pass a second strict contract-entailment critic before they can influence the verdict.

Local verification:
- `python -m pytest`: **63 passed in 55.76s**;
- targeted case_001: two executable failures were both rejected as `unsupported_counterexample`;
- targeted case_002: one generated candidate reached the Critic and was rejected as unsupported;
- targeted case_003: two generated candidates reached the Critic and were both rejected;
- targeted case_006: one generated candidate reached the Critic and was rejected;
- targeted case_007: the candidate produced `invalid_execution`, so the Critic was not called.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- challenge generation failures: **7**
- challenge critic failures: **0**
- average runtime: **27.624s/case**

Interpretation:
- the Critic was operationally reliable (zero critic failures) but systematically rejected every patch-failing generated assertion it saw;
- the system therefore stayed safe but remained incapable of recovering the intentionally hidden partial/regression cases;
- latency worsened because the pipeline paid for both free-form test generation and semantic criticism;
- after 3.1–3.3, further prompt-format tuning is no longer justified. The structural problem is that the model is being asked to author executable pytest syntax and semantic expectations at the same time.

Decision: **stop the 3.x prompt-tuning line here.** Preserve 3.3 as evidence that independent criticism alone cannot rescue low-quality free-form generated tests.

## Advanced Iteration 4 — intent-first Challenger + deterministic test compiler

Hypothesis: remove Python test authoring from the Challenger entirely. Ask the model only for a typed semantic test intent, validate that intent against the public contract, then compile the test deterministically. This should reduce syntax/API hallucination and let the Critic judge a compact semantic object rather than arbitrary generated source code.

Structural changes:
- the harness deterministically extracts contract IDs from the public issue and callable targets from the public test import surface;
- Challenger returns only: `kind`, `contract_id`, `target`, JSON arguments, a typed expectation (`equals`, `raises`, or `len_lte_arg`), and rationale;
- Challenger never emits pytest/Python source;
- a separate intent Critic judges whether the structured input/expectation is directly supported by the selected public contract;
- unsupported intents are rejected before execution and can feed one bounded retry;
- supported intents are compiled by deterministic Python into a focused pytest test;
- generated code therefore cannot invent imports, arbitrary helper logic, or malformed test syntax;
- deterministic execution on original and patch still decides regression/remaining/survived evidence;
- a negative verdict requires critic-approved executable evidence;
- `complete_fix` requires two distinct critic-approved nearby intents to survive, preventing a single easy generated case from certifying completeness;
- oracle and hidden tests remain unavailable to Challenger, Critic, compiler, and verifier.

Success criteria against the frozen Benchmark v2 history:
- recover at least some of case_002/case_003/case_006/case_007 as critic-approved counterexamples;
- materially exceed the 30.0% accuracy plateau from 3.1–3.3;
- retain FAR below Iteration 2.4's 57.1%;
- reduce invalid-execution failures because test source is compiled deterministically rather than authored by the model.

Status: implementation complete; local verification pending. Do not claim an Iteration 4 improvement until the human supplies a clean local run.
