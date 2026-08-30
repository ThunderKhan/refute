# Agent Trajectories

This file records representative coding-agent trajectories used to build `refute` during the Frontier Engineering Challenge 2026. Portable normalized trace packages are stored under `traces/`; they preserve observable prompts/instructions, actions, tool feedback, failures, retries, verification, and human checkpoints without reconstructing hidden reasoning.

---

## trajectory-001 — Milestone 1 deterministic spine

Human instruction: `go ahead and implement milestone one I give you permission to push code to github`.

The round established package configuration, verification models, benchmark loading, deterministic command execution, case inspection, seed fixtures, and tests. The human later verified `8 passed in 3.90s` and original-fail/patched-pass execution on `case_001`.

Normalized trace: `traces/trace-001-milestone-1/`.

---

## trajectory-002 — Static-review baseline

The static LLM baseline, provider abstraction, issue+diff prompting, structured verdict parsing, and persisted artifacts were added. Frozen Baseline v1 later measured 10.0% accuracy, 57.1% FAR, and 2.405s/case.

Normalized trace: `traces/trace-002-static-baseline/`.

---

## trajectory-003 — Evaluator and architecture backbone

The ten-case benchmark, batch evaluator, evidence store, orchestration state machine, package boundaries, and architecture documentation were added.

Normalized trace: `traces/trace-003-evaluator-architecture/`.

---

## trajectory-004 — Advanced Iteration 1

Investigator + deterministic execution + evidence-constrained verifier measured 40.0% accuracy, 28.6% FAR, and 5.641s/case.

Normalized trace: `traces/trace-004-advanced-iteration-1/`.

---

## trajectory-005 — Advanced Iteration 2

Generated reproduction and bounded retry reduced FAR to 0.0% but produced 10.0% accuracy and 36.569s/case because fail/fail generated tests were treated too strongly.

Normalized trace: `traces/trace-005-reproduction-loop/`.

---

## trajectory-006 — Advanced Iteration 2.1

Only original FAIL + patch PASS became successful reproduction evidence. Result: 40.0% accuracy, 0.0% FAR, 52.584s/case.

Normalized trace: `traces/trace-006-iteration-2-1/`.

---

## trajectory-007 — Advanced Iteration 2.2

Evidence weighting and stagnation stopping measured 30.0% accuracy, 0.0% FAR, and 50.863s/case.

Normalized trace: `traces/trace-007-iteration-2-2/`.

---

## trajectory-008 — Advanced Iteration 2.3

Deterministic pytest failure-set deltas reduced runtime to 11.657s/case and produced 50.0% accuracy with one provider error.

Normalized trace: `traces/trace-008-iteration-2-3/`.

---

## trajectory-009 — Advanced Iteration 2.4

Test-first routing produced 100.0% on Benchmark v1 at 1.019s/case, but every case was solved without agent calls. This became evidence that Benchmark v1 leaked too much verdict information through public tests.

Normalized trace: `traces/trace-009-iteration-2-4/`.

---

## trajectory-010 — Benchmark v2 oracle separation

Human instruction: `okay do it`.

Public cases were separated from evaluator-only expected verdicts and hidden nearby tests. Frozen Baseline v2 measured **10.0% accuracy / 57.1% FAR / 2.527s**, while unchanged Iteration 2.4 dropped to **60.0% / 57.1% FAR / 0.929s**, confirming the Benchmark v1 saturation.

Normalized trace: `traces/trace-010-benchmark-v2/`.

---

## trajectory-011 — Advanced Iteration 3: Challenger

Human instruction: `okay go ahead`.

Conditional adversarial nearby-test generation measured **40.0% accuracy, 0.0% FAR, 42.9% Challenger case yield, five counterexamples, and 14.774s/case**. Safety improved, but weakly grounded fail/fail challenges created false negatives.

Normalized trace: `traces/trace-011-iteration-3/`.

---

## trajectory-012 — Advanced Iteration 3.1: exact-quote grounding

Iteration 3.1 required one typed candidate and an exact issue quote. Local measurement fell to **30.0% accuracy, 0.0% FAR, 0.0% yield, and 20.438s/case**. The interface was too brittle for the small local model: most suite-repaired cases exhausted generation attempts without executable evidence.

Normalized trace: `traces/trace-012-iteration-3-1/`.

---

## trajectory-013 — Advanced Iteration 3.2: deterministic contract IDs

Exact quote copying was replaced with deterministic issue-contract spans and model-selected IDs; the Investigator call was removed from the challenge path. The human verified **60 tests passed in 47.71s**. Benchmark v2 still measured **30.0% accuracy, 0.0% FAR, 0.0% yield, 0 counterexamples, 9 generation failures, and 25.966s/case**.

The main failure shifted from quote-format brittleness to evidence semantics: generated tests often executed but could not safely be treated as remaining requirements. This showed that grounding reference and evidence qualification are distinct problems.

Normalized trace: `traces/trace-013-iteration-3-2/`.

---

## trajectory-014 — Advanced Iteration 3.3: contract-entailment critic

Iteration 3.3 retains deterministic contract IDs but separates proposal from evidence qualification. A Challenger still proposes nearby tests, but any generated test that fails on the patch must pass a second strict Critic which sees only the selected public contract span and the test code. Unsupported executable failures are rejected and can feed a bounded retry instead of directly affecting the verdict.

Regression and remaining-requirement evidence therefore require both deterministic execution shape and independent contract support. Patch-passing challenges avoid the extra Critic call. Oracle and hidden tests remain unavailable to both agents.

Local verification is pending; no improvement claim is made yet.

Normalized trace: `traces/trace-014-iteration-3-3/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh. Preserve exact human instructions, observable repository/tool actions, failures/retries, verification, measurable outcomes, and relevant model/provider metadata. Do not invent historical gaps, include credentials, or expose private chain-of-thought.
