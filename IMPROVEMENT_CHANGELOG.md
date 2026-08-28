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

Change from baseline: +30 percentage points accuracy; false acceptance approximately halved; runtime increased by 3.236s/case.

Decision: keep Investigator + deterministic runtime evidence.

## Advanced Iteration 2 — generated reproduction + bounded retry

Hypothesis: an agent/tool feedback loop that generates and executes reported-bug reproductions will improve on Iteration 1.

Result:
- verdict accuracy: **10.0%**
- false acceptance rate: **0.0%**
- average runtime: **36.569s/case**

Observed failure: generated tests that failed on both original and patched implementations were incorrectly treated as successful reproductions. This made the system safer against false approvals but much less accurate and substantially slower.

Decision: **do not keep Iteration 2 semantics as the final design**. Preserve it as a negative experiment. Fix evidence semantics before adding another agent.

## Advanced Iteration 2.1 — discriminating reproduction semantics

Hypothesis: only accepting original-FAIL/patch-PASS generated tests as successful reproductions will recover accuracy while retaining the safer approval behavior.

Result:
- verdict accuracy: **40.0%**
- false acceptance rate: **0.0%**
- average runtime: **52.584s/case**

Observed failure: a non-discriminating generated test could still influence the model toward an unsupported negative verdict even when the patched deterministic suite passed. Runtime also increased further due to repeated reproduction attempts.

Decision: keep discriminating reproduction semantics, but downgrade non-discriminating attempts to diagnostic-only evidence and cut clearly stagnant retries.

## Advanced Iteration 2.2 — evidence weighting + stagnation stop

Hypothesis: explicitly weighting generated evidence and preventing diagnostic-only failures from driving negative verdicts will preserve safety while improving grounding; stopping after repeated non-discriminating attempts should reduce wasted runtime.

Changes:
- `discriminating` reproduction: high-confidence evidence;
- `non_discriminating`: diagnostic-only, cannot by itself establish patch failure;
- `not_reproduced`: no negative evidence against the patch;
- deterministic weighted-verdict gate;
- early stop after two consecutive non-discriminating attempts;
- separate `advanced_iteration_2_2` evaluation artifacts.

Result: **pending local benchmark run**.

Decision: pending measured evidence. Challenger remains intentionally deferred until this evidence layer is stable.
