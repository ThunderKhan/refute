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

Observed case behavior:
- `case_002` -> deterministic `partial_fix` in 4.10s;
- `case_003` -> deterministic `regression_introduced` in 3.06s;
- `case_004` -> deterministic `ineffective_fix` in 3.43s;
- `case_006` -> deterministic `partial_fix` in 4.74s;
- `case_008` -> deterministic `ineffective_fix` in 5.72s;
- `case_007` still failed before deterministic evidence because the Investigator was invoked first and timed out;
- suite-repaired cases (`case_001`, `case_005`, `case_009`) still paid for reproduction/verifier calls and often returned `inconclusive` despite all observed failing tests being repaired;
- `case_010` remained semantically ambiguous.

Decision: keep the test-delta engine, but move deterministic execution ahead of the Investigator. The observed suite itself should count as a discriminating executable witness when named failures disappear and no new failures appear. If both original and patched suites already pass, remain `inconclusive` rather than fabricate causality.

## Advanced Iteration 2.4 — test-first routing

Hypothesis: route deterministic execution before any agent call. Resolve mechanically decisive cases without the Investigator, Reproducer, or Verifier; invoke agents only for genuinely ambiguous deltas.

Changes:
- original and patched suites execute before the Investigator;
- deterministic partial/ineffective/regression deltas return immediately;
- original FAIL -> patched PASS with observed fixed test IDs and no remaining/new failures returns `complete_fix` relative to the observed suite;
- original PASS + patched PASS returns `inconclusive` because the reported bug was not reproduced by available deterministic evidence;
- Investigator, generated reproduction, and semantic verifier become conditional fallback stages only;
- provider outages can no longer block mechanically decisive cases;
- separate `advanced_iteration_2_4` artifacts preserve the experiment.

Result: **pending local verification and benchmark run**.

Important benchmark finding: if Iteration 2.4 nearly saturates the current ten cases without using agents, that is evidence the current benchmark exposes too much verdict information through public tests. In that event, do not treat the score as the final advanced-agent result; redesign the benchmark with public reproduction tests separated from hidden evaluation oracles before adding the Challenger.
