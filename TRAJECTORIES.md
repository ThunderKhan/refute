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

This round added the ten-case benchmark, batch baseline evaluator, evidence store, orchestration state machine, package boundaries, and architecture documentation. The human ran frozen Baseline v1 with `qwen3:0.6b`: 10.0% verdict accuracy, 57.1% false acceptance, 2.405s average runtime.

Normalized trace: `traces/trace-003-evaluator-architecture/`.

---

## trajectory-004 — Advanced Iteration 1

Human instruction: `okay let's implement this`.

Iteration 1 added the Investigator, deterministic existing-test execution, evidence persistence, and evidence-constrained verifier while intentionally excluding generated reproduction and Challenger behavior. The human measured 40.0% verdict accuracy, 28.6% false acceptance, and 5.641s average runtime on the same ten cases.

Normalized trace: `traces/trace-004-advanced-iteration-1/`.

---

## trajectory-005 — Advanced Iteration 2: reproduction loop

Human instruction: `implement it`.

Iteration 2 added generated pytest reproduction, bounded execution-feedback retry, generated-test safety validation, provider/malformed-output recovery, a deterministic verdict gate, batch progress/checkpointing, and configurable LLM timeouts. During local validation, several real failures were preserved and fixed: malformed JSON, unusable model output, provider timeouts, a verifier contradiction, and slow opaque batch behavior.

The final clean ten-case Iteration 2 run with `qwen3:0.6b` measured 10.0% verdict accuracy, 0.0% false acceptance, and 36.569s average runtime. This was a negative capability experiment: the system became safer against false approval but much less accurate and much slower.

The key semantic flaw discovered was that a generated test failing on both original and patch was still labeled a successful reproduction. That finding directly motivated Iteration 2.1.

Normalized trace: `traces/trace-005-reproduction-loop/`.

---

## trajectory-006 — Advanced Iteration 2.1: discriminating reproduction semantics

Human instruction: `Start with 2.1 and fix the errors`.

Iteration 2.1 repaired the reproduction semantics: only **original FAIL + patch PASS** counts as a successful generated reproduction. Original FAIL + patch FAIL/timeout is non-discriminating and feeds both outputs back to the next attempt; original PASS/timeout is treated as not reproduced.

The human verified `31 passed in 18.56s` and then ran the ten-case benchmark with `qwen3:0.6b`. Iteration 2.1 measured 40.0% verdict accuracy, 0.0% false acceptance, and 52.584s average runtime. This recovered Iteration 1's accuracy while retaining Iteration 2's zero false-acceptance result, but runtime became substantially worse.

The single-case validation exposed another flaw: a non-discriminating generated test could still pull the model toward an unsupported negative verdict even though the patched deterministic suite passed. That finding motivated evidence weighting in Iteration 2.2.

Normalized trace: `traces/trace-006-iteration-2-1/`.

---

## trajectory-007 — Advanced Iteration 2.2: evidence weighting

Human instruction: `go ahead with 2.2`.

Iteration 2.2 assigns explicit confidence semantics to generated evidence:

- **discriminating** = original FAIL + patch PASS, high-confidence evidence;
- **non_discriminating** = original FAIL + patch FAIL/timeout, diagnostic-only evidence;
- **not_reproduced** = original PASS/timeout, no negative evidence against the patch.

A deterministic weighted-verdict gate prevents diagnostic-only or not-reproduced generated tests from justifying `partial_fix`, `ineffective_fix`, or `regression_introduced` when the patched deterministic suite passes and no high-confidence reproduction exists. The raw model proposal remains preserved in evidence.

Iteration 2.2 also adds an early stagnation stop after two consecutive non-discriminating attempts, reducing wasted Reproducer calls when the local model is clearly not converging. Iterations 1, 2, and 2.1 remain available unchanged for ablation comparison, and 2.2 writes to its own evaluation directory.

Local verification is pending and is recorded in `traces/trace-007-iteration-2-2/verification.txt`.

Normalized trace: `traces/trace-007-iteration-2-2/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh. Preserve exact human instructions, observable repository/tool actions, failures/retries, verification, measurable outcomes, and relevant model/provider metadata. Do not invent historical gaps, include credentials, or expose private chain-of-thought.
