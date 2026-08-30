# Agent Trajectories

This file records representative coding-agent trajectories used to build `refute` during the Frontier Engineering Challenge 2026. Portable normalized trace packages are stored under `traces/`; they preserve observable prompts/instructions, actions, tool feedback, failures, retries, verification, and human checkpoints without reconstructing hidden reasoning.

---

## trajectory-001 — Milestone 1 deterministic spine

Human instruction: `go ahead and implement milestone one I give you permission to push code to github`.

The round established package configuration, verification models, benchmark loading, deterministic command execution, case inspection, seed fixtures, and tests. The human later verified `8 passed in 3.90s` and original-fail/patched-pass execution on `case_001`.

Normalized trace: `traces/trace-001-milestone-1/`.

---

## trajectory-002 — Static-review baseline

Human instruction: `alright go ahead and implement the next step`.

The round added the intentionally limited static LLM baseline, provider abstraction, issue+diff prompting, structured verdict parsing, persisted prompt/response/result artifacts, CLI support, and fake-LLM tests. The human verified `12 passed in 3.33s`; the preliminary three-case run scored 0/3.

Normalized trace: `traces/trace-002-static-baseline/`.

---

## trajectory-003 — Evaluator and architecture backbone

Human instruction: `okay go ahead and implement add whatever is not addeed for milestone 1 and 2 for our revised architecture`.

This round added the ten-case benchmark, batch baseline evaluator, evidence store, orchestration state machine, package boundaries, and architecture documentation. Frozen Baseline v1 measured 10.0% verdict accuracy, 57.1% false acceptance, and 2.405s average runtime.

Normalized trace: `traces/trace-003-evaluator-architecture/`.

---

## trajectory-004 — Advanced Iteration 1

Iteration 1 added the Investigator, deterministic existing-test execution, evidence persistence, and evidence-constrained verifier. Result: 40.0% accuracy, 28.6% false acceptance, 5.641s average runtime.

Normalized trace: `traces/trace-004-advanced-iteration-1/`.

---

## trajectory-005 — Advanced Iteration 2

Generated reproduction and bounded retry reduced false acceptance to 0.0% but produced 10.0% accuracy and 36.569s runtime because fail/fail generated tests were treated too strongly.

Normalized trace: `traces/trace-005-reproduction-loop/`.

---

## trajectory-006 — Advanced Iteration 2.1

Only original FAIL + patch PASS became successful reproduction evidence. Result: 40.0% accuracy, 0.0% FAR, 52.584s runtime.

Normalized trace: `traces/trace-006-iteration-2-1/`.

---

## trajectory-007 — Advanced Iteration 2.2

Evidence weighting and stagnation stopping measured 30.0% accuracy, 0.0% FAR, and 50.863s runtime.

Normalized trace: `traces/trace-007-iteration-2-2/`.

---

## trajectory-008 — Advanced Iteration 2.3

Deterministic pytest failure-set deltas reduced runtime to 11.657s and produced 50.0% accuracy with one provider error.

Normalized trace: `traces/trace-008-iteration-2-3/`.

---

## trajectory-009 — Advanced Iteration 2.4

Test-first routing produced 100.0% on Benchmark v1 at 1.019s/case, but every case was solved without agent calls. This became evidence that Benchmark v1 leaked too much verdict information through public tests.

Normalized trace: `traces/trace-009-iteration-2-4/`.

---

## trajectory-010 — Benchmark v2 oracle separation

Human instruction: `okay do it`.

Public cases were separated from evaluator-only expected verdicts and hidden nearby tests. The human verified 48 tests, the ten-case builder, and the separation audit. Frozen Baseline v2 measured **10.0% / 57.1% FAR / 2.527s**, while unchanged Iteration 2.4 dropped to **60.0% / 57.1% FAR / 0.929s**, confirming the Benchmark v1 saturation.

Normalized trace: `traces/trace-010-benchmark-v2/`.

---

## trajectory-011 — Advanced Iteration 3: Challenger

Human instruction: `okay go ahead`.

Iteration 3 added conditional adversarial nearby-test generation after a public trigger was repaired. A clean Benchmark v2 run measured **40.0% accuracy, 0.0% FAR, 42.9% Challenger case yield, five executable counterexamples, and 14.774s runtime**.

The safety gain was real, but candidate grounding was too weak. True complete fixes were sometimes labeled partial because arbitrary fail/fail generated tests counted as remaining-bug evidence, while several suite-repaired cases produced no usable challenge candidate. This was preserved as a safety-positive / accuracy-negative experiment.

Normalized trace: `traces/trace-011-iteration-3/`.

---

## trajectory-012 — Advanced Iteration 3.1: grounded Challenger

The clean Iteration 3 result motivated a narrower evidence contract. Iteration 3.1 generates one candidate per call, requires a typed intent (`remaining_requirement` or `regression_guard`), and requires an exact short quote copied from the public issue report. A deterministic gate rejects invented grounding before test execution.

Original PASS + patch FAIL remains strong regression evidence. Original FAIL + patch FAIL can support `partial_fix` only for an explicitly grounded remaining requirement. Invalid/non-grounded outputs can be retried once; survived grounded tests can support a bounded `complete_fix`. Oracle and hidden tests remain unavailable to the verification path.

Local verification is pending. No improvement claim is made until the measured Benchmark v2 run is supplied.

Normalized trace: `traces/trace-012-iteration-3-1/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh. Preserve exact human instructions, observable repository/tool actions, failures/retries, verification, measurable outcomes, and relevant model/provider metadata. Do not invent historical gaps, include credentials, or expose private chain-of-thought.
