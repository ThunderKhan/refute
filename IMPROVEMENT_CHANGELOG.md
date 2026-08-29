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

Observed failure: non-discriminating generated tests could still influence unsupported negative verdicts, and retry cost became excessive.

Decision: keep discriminating semantics, but weight evidence and reduce wasted retries.

## Advanced Iteration 2.2 — evidence weighting + stagnation stop

Hypothesis: confidence weighting plus early stagnation stopping will preserve safety while improving grounding and runtime.

Result:
- verdict accuracy: **30.0%**
- false acceptance rate: **0.0%**
- average runtime: **50.863s/case**

Observed behavior: safety remained strong, but accuracy regressed and runtime barely improved. The workflow still paid for model reasoning even when existing pytest results already contained useful mechanical deltas.

Decision: move deterministic suite analysis earlier.

## Advanced Iteration 2.3 — deterministic test-delta engine + conditional reproduction

Hypothesis: mechanically comparing pytest failure identifiers between original and patched suites will resolve observed partial/ineffective/regression outcomes more accurately and cheaply, while reserving generated reproduction for suite-repaired or ambiguous cases.

Result from the clean local run:
- completed cases: **9/10**
- errors: **1** (`case_007` Investigator timeout)
- verdict accuracy: **50.0%** over the ten-case evaluator output
- false acceptance rate: **0.0%**
- average runtime: **11.657s/case**

Decision: keep the test-delta engine, but move deterministic execution ahead of the Investigator.

## Advanced Iteration 2.4 — test-first routing

Hypothesis: route deterministic execution before any agent call. Resolve mechanically decisive cases without the Investigator, Reproducer, or Verifier; invoke agents only for genuinely ambiguous deltas.

Local verification:
- `python -m pytest`: **43 passed in 35.58s**;
- `case_001`: deterministic `complete_fix`, no Investigator/Reproducer/Verifier;
- `case_007`: deterministic `regression_introduced`, no Investigator/Reproducer/Verifier;
- `case_010`: deterministic `inconclusive`, no Investigator/Reproducer/Verifier.

Benchmark v1 result:
- completed cases: **10/10**
- errors: **0**
- verdict accuracy: **100.0%**
- false acceptance rate: **0.0%**
- average runtime: **1.019s/case**

Interpretation: this is **not** a valid final agentic improvement result. Iteration 2.4 solved all ten cases without agent calls, demonstrating that Benchmark v1 exposes enough oracle information through its public test suite for deterministic before/after failure analysis to reconstruct the expected verdicts.

Decision: preserve 2.4 as a systems-engineering and benchmark-diagnostic result, but do not use its 100.0% as the final hackathon agentic claim.

## Benchmark v2 — oracle separation

Hypothesis: separating public reported-bug evidence from evaluator-only ground truth will prevent deterministic suite analysis from reading the answer directly and make semantic/adversarial agent capability measurable again.

Implemented design:
- public cases use `case.json`, which contains case identity and public test command but **cannot contain `expected_verdict`**;
- `VerificationCase.expected_verdict` is optional so oracle-free cases can flow through the verification pipeline without ground truth;
- the case loader rejects an inline oracle in public `case.json`;
- evaluator-only verdicts live in `eval/benchmark_v2/oracles.json`;
- evaluator-only nearby/boundary/regression tests live in `eval/benchmark_v2/hidden_tests.json`;
- `scripts/build_benchmark_v2.py` reproducibly builds ten public cases from the frozen v1 implementations while replacing the overexposing test suites with narrow reported-trigger tests;
- baseline and advanced evaluators accept `--oracle-root` and resolve the oracle only after the verification result exists;
- Benchmark v2 reports are written separately (`baseline_v2`, `advanced_iteration_*_benchmark_v2`) so v1 measurements cannot be overwritten;
- generated public case directories are ignored by Git because they are reproducibly derived artifacts; the builder and evaluator-only oracle material are tracked.

Representative separation:
- `case_002`: public lower-boundary test is repaired by the patch, while hidden upper-boundary test retains the `partial_fix` oracle;
- `case_003`: public surrounding-whitespace test is repaired, while hidden internal-space preservation exposes the regression;
- `case_007`: public division-by-zero behavior is repaired, while hidden invalid-operand behavior exposes the overly broad exception handler;
- `case_010`: public deterministic behavior passes on both versions and the oracle remains `inconclusive` because the intermittent report is not reproduced.

Local verification:
- `python -m pytest`: **48 passed in 31.98s**;
- `python scripts/build_benchmark_v2.py`: built **10** public cases;
- separation audit: **PASSED**;
- `refute inspect benchmark_v2\case_002`: oracle withheld, original FAIL, patch PASS.

### Frozen Baseline v2

First clean run on the oracle-separated benchmark:
- model: `qwen3:0.6b`
- cases: **10**
- oracle separated: **yes**
- verdict accuracy: **10.0%**
- false acceptance rate: **57.1%**
- average runtime: **2.527s/case**

Decision: **freeze Baseline v2 at 10.0% accuracy / 57.1% FAR / 2.527s average runtime.** Do not tune or rerun the baseline to improve it after seeing advanced Benchmark v2 outcomes without explicit versioning.

Next experiment: run Advanced Iteration 2.4 unchanged on Benchmark v2 using the separated oracle. This is an ablation check. If its Benchmark v2 score drops substantially from the 100.0% Benchmark v1 result, that directly confirms the earlier saturation came from public-test leakage. Challenger work starts only after this measurement is frozen.
