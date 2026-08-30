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

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **0.0%**
- executable counterexamples: **0**
- challenge generation failures: **9**
- average runtime: **25.966s/case**

Interpretation: deterministic contract IDs improved grounding ergonomics but did not solve semantic evidence qualification.

Decision: preserve 3.2 as a negative experiment.

## Advanced Iteration 3.3 — contract-entailment critic

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

Interpretation: the Critic was operationally reliable but systematically rejected patch-failing generated assertions. Independent criticism kept the system safe but could not rescue low-quality free-form test generation.

Decision: stop the 3.x prompt-tuning line.

## Advanced Iteration 4 — intent-first Challenger

Iteration 4 removed Python/pytest authoring from the model. Challenger emitted a typed semantic intent, a separate Critic validated it, and the harness compiled pytest deterministically.

Benchmark v2 result:
- completed cases: **10/10**
- errors: **0**
- accuracy: **30.0%**
- FAR: **0.0%**
- Challenger case yield: **14.3%**
- executable counterexamples: **1**
- challenge generation failures: **9**
- critic failures: **0**
- critic rejections: **1**
- average runtime: **13.026s/case**

Interpretation: deterministic test compilation roughly halved runtime versus 3.3, but the small model still had to invent semantic assertions and remained unreliable. A false regression on a true complete fix also showed that structured intent alone did not solve semantic hallucination.

Decision: remove semantic assertion invention from the model too.

## Advanced Iteration 5 — deterministic contract probes + agent prioritization

Hypothesis: compile a small, auditable pool of nearby probes directly from the public issue contract and public API, then use the language model only to prioritize probe IDs. Deterministic execution, not the model, decides whether each probe survives or falsifies the patch.

Structural changes:
- public tests still run first, and only `suite_repaired` cases spend challenge budget;
- a deterministic compiler recognizes a deliberately small MVP contract vocabulary and emits contract-grounded probes;
- probes include inclusive range boundaries, preserved internal whitespace, trim/lowercase behavior, whitespace-collapse behavior, small non-negative length limits, and exception preservation;
- the model receives only probe IDs/descriptions and returns a priority order;
- if planner output is unusable, the harness can fall back to deterministic probe order and records that fallback;
- the model no longer authors Python, pytest, imports, arguments, expected values, or exception semantics;
- probe source is compiled and executed deterministically on original and patched code;
- `complete_fix` requires two independent survived probes;
- oracle verdicts and hidden tests remain evaluator-only and are never loaded by the probe compiler, planner, or verification path.

Clean local verification:
- `python -m pytest`: **72 passed in 63.16s**;
- all five targeted challenge cases produced the intended evidence with **0 generation failures** and **0 planner fallbacks**;
- case_001: `complete_fix` after two survived probes;
- case_002: `partial_fix` from a remaining upper-boundary failure;
- case_003: `regression_introduced` from internal-space preservation;
- case_006: `partial_fix` from a tiny-limit invariant failure;
- case_007: `regression_introduced` from exception-preservation evidence.

### Frozen Benchmark v2 result

- completed cases: **10/10**
- errors: **0**
- verdict accuracy: **100.0%**
- false acceptance rate: **0.0%**
- Challenger case yield: **57.1%**
- executable counterexamples: **4**
- challenge generation failures: **0**
- planner fallback cases: **0**
- average runtime: **5.077s/case**

Every Benchmark v2 case was classified correctly:
- complete fixes: case_001, case_005, case_009;
- partial fixes: case_002, case_006;
- regressions: case_003, case_007;
- ineffective fixes: case_004, case_008;
- inconclusive: case_010.

### Measured improvement on the same oracle-separated Benchmark v2

- Baseline v2: **10.0% accuracy / 57.1% FAR / 2.527s**
- Iteration 2.4: **60.0% accuracy / 57.1% FAR / 0.929s**
- Iteration 5: **100.0% accuracy / 0.0% FAR / 5.077s**

Interpretation:
- versus Baseline v2, Iteration 5 improved verdict accuracy by **90 percentage points** and reduced FAR by **57.1 percentage points**;
- versus the deterministic 2.4 ablation, Iteration 5 improved accuracy by **40 percentage points** and reduced FAR from **57.1% to 0.0%**;
- the price is higher runtime than the static baseline/test-only ablation, but substantially lower runtime than Iterations 3–4;
- the key improvement did not come from a better prompt. It came from moving mechanically derivable semantics out of the model and leaving the model a narrow prioritization decision.

Decision: **freeze Iteration 5 as the final advanced system for the hackathon submission.** Further work should focus on reproducibility, broader external validation, documentation, and demo quality rather than benchmark-specific tuning.

Important limitation: Benchmark v2 has ten controlled synthetic cases and the contract compiler intentionally supports a small MVP vocabulary. The 100.0% result is a benchmark result, not a claim that `refute` can verify arbitrary software patches with 100% accuracy.
