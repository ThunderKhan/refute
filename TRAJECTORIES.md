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

### Human instruction

> "Start with 2.1 and fix the errors"

### Objective

Repair the evidence semantics before adding another agent. A generated test is now accepted as reproduction evidence only when it discriminates between implementations.

### Observable implementation changes

- added `src/refute/verify_v21.py`, leaving Iteration 2 available for reproducible comparison;
- defined the only successful reproduction pattern as **original FAIL + patch PASS**;
- changed **original FAIL + patch FAIL/timeout** into a non-discriminating outcome that feeds both execution outputs back to the next Reproducer attempt;
- changed **original PASS/timeout** into a failed reproduction attempt that triggers retry;
- added explicit `original_failed`, `patch_passed`, and `discriminating` evidence fields;
- updated CLI support to accept `--iteration 2.1` and made 2.1 the default advanced path;
- updated the batch evaluator to preserve separate `advanced_iteration_2_1` artifacts rather than overwriting Iteration 2;
- added tests proving both-fail attempts are retried and only original-fail/patch-pass is accepted;
- created the normalized trace during implementation.

### Experimental question

Does correcting the semantics of generated reproduction recover useful verdict accuracy while preserving Iteration 2's reduction in unsafe `complete_fix` approvals?

### Verification status

Local verification is pending. Required commands are recorded in `traces/trace-006-iteration-2-1/verification.txt`.

Normalized trace: `traces/trace-006-iteration-2-1/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh. Preserve exact human instructions, observable repository/tool actions, failures/retries, verification, measurable outcomes, and relevant model/provider metadata. Do not invent historical gaps, include credentials, or expose private chain-of-thought.
