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

Iteration 3.1 required one typed candidate and an exact issue quote. Local measurement fell to **30.0% accuracy, 0.0% FAR, 0.0% yield, and 20.438s/case**. The interface was too brittle for the small local model.

Decision: preserve 3.1 as a negative experiment.

## Advanced Iteration 3.2 — deterministic contract IDs

Exact quote copying was replaced with deterministic issue-contract spans and model-selected IDs; the Investigator call was removed from the challenge path. Benchmark v2 still measured **30.0% accuracy, 0.0% FAR, 0.0% yield, 0 counterexamples, 9 generation failures, and 25.966s/case**.

Decision: preserve 3.2 as a negative experiment.

## Advanced Iteration 3.3 — contract-entailment critic

A separate Critic was introduced to qualify patch-failing generated assertions against the selected public contract. Benchmark v2 measured **30.0% accuracy, 0.0% FAR, 0.0% yield, 0 counterexamples, 7 generation failures, 0 critic failures, and 27.624s/case**.

Decision: stop the 3.x prompt-tuning line.

## Advanced Iteration 4 — intent-first Challenger

Iteration 4 removed Python/pytest authoring from the model. Challenger emitted a typed semantic intent, a Critic validated it, and deterministic Python compiled it into pytest.

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
- versus Iteration 2.4, Iteration 5 improved accuracy by **40 percentage points** and reduced FAR from **57.1% to 0.0%**;
- the price is higher runtime than the static baseline/test-only ablation, but substantially lower runtime than Iterations 3–4;
- the key improvement came from changing the responsibility boundary: mechanically derivable semantics moved out of free-form model generation and into deterministic probes.

Decision: **freeze Iteration 5 as the final advanced system for the hackathon submission.** Further work should focus on reproducibility, broader external validation, documentation, and demo quality rather than benchmark-specific tuning.

Important limitation: Benchmark v2 has ten controlled synthetic cases and the contract compiler intentionally supports a small MVP vocabulary. The 100.0% result is a benchmark result, not a claim that `refute` can verify arbitrary software patches with 100% accuracy.

## Post-freeze ablation — remove agent probe prioritization

After Iteration 5 was frozen, a controlled component ablation replaced the LLM planner with deterministic compiler order while keeping the same deterministic contract compiler, probe budget (`2`), probe execution, classification rules, and verdict thresholds.

Observed Benchmark v2 result:

- cases: **10/10**
- verdict accuracy: **100.0%**
- false acceptance rate: **0.0%**
- challenge counterexamples: **4**
- average runtime: **2.043s/case**
- model/provider calls: **0**

Interpretation: **on Benchmark v2, agent probe prioritization was not necessary to achieve the final 100% accuracy under the two-probe budget.** The deterministic contract compiler plus deterministic probe order reproduced every verdict and all four counterexamples.

This null ablation result changes the attribution of the final benchmark gain: Benchmark v2 strongly supports the move from model-authored semantics to deterministic contract-derived evidence, but it does not demonstrate that the LLM planner itself improved verdict accuracy.

Decision: preserve the result and do not retune the verifier. Validate both the frozen Iteration 5 system and the deterministic-order ablation on a post-freeze unseen holdout.

## Post-freeze Holdout v1 — first unseen evaluation

Holdout v1 contains **12 new cases** authored only after Iteration 5 and the Benchmark v2 planner ablation were frozen. The builder/audit were committed before evaluation, and the public material was frozen with SHA-256:

```text
c2604717e69fb99c2d30e17ee4f586d4463e3bd032e55344684e9db9992b5cb1
```

The audit confirmed 12 public cases, 12 evaluator-only oracles, and no verdict oracle in public material.

The first static-baseline attempt timed out at the local model provider before producing a result. This is recorded as an execution failure and is not converted into an accuracy score.

### Deterministic-order ablation on Holdout v1

- completed cases: **12/12**
- verdict accuracy: **83.3%**
- false acceptance rate: **20.0%**
- challenge counterexamples: **6**
- average runtime: **2.698s/case**
- wrong cases: `holdout_010`, `holdout_012`

### Frozen Iteration 5 on Holdout v1

- completed cases: **12/12**
- errors: **0**
- verdict accuracy: **83.3%**
- false acceptance rate: **20.0%**
- Challenger case yield: **60.0%**
- challenge counterexamples: **6**
- planner/generation failures: **2**
- planner fallback cases: **2**
- average runtime: **9.989s/case**
- wrong cases: `holdout_010`, `holdout_012`

Interpretation:
- the post-freeze set exposes a real generalization gap: **100.0% → 83.3% accuracy** and **0.0% → 20.0% FAR** relative to Benchmark v2;
- nevertheless, 10 of 12 unseen cases were classified correctly without verifier tuning after the holdout was frozen;
- the same two cases were missed by both deterministic ordering and the LLM planner;
- the planner again provided **no measured verdict improvement** under the tested two-probe budget;
- the planner path was substantially slower and incurred two provider/planner failures that triggered deterministic fallback.

Decision: do **not** tune Iteration 5 to Holdout v1. Preserve the result as the project's strongest evidence about external validity within the stated synthetic MVP domain.

Updated architectural lesson:

> When requirements are mechanically derivable, deterministic evidence should own them completely. Agentic reasoning should be reserved for ambiguity that deterministic machinery cannot represent, such as the bounded nearby-test selection used in the real-repository workflow.
