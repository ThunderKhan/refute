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

Iteration 2 added generated pytest reproduction, bounded execution-feedback retry, generated-test safety validation, provider/malformed-output recovery, a deterministic verdict gate, batch progress/checkpointing, and configurable LLM timeouts. The final clean ten-case run measured 10.0% verdict accuracy, 0.0% false acceptance, and 36.569s average runtime. The main discovered flaw was that generated tests failing on both original and patch were treated as successful reproductions.

Normalized trace: `traces/trace-005-reproduction-loop/`.

---

## trajectory-006 — Advanced Iteration 2.1: discriminating reproduction semantics

Human instruction: `Start with 2.1 and fix the errors`.

Only original FAIL + patch PASS now counts as a successful generated reproduction. The human verified `31 passed in 18.56s`; the ten-case run measured 40.0% accuracy, 0.0% false acceptance, and 52.584s average runtime. The experiment recovered accuracy but exposed that diagnostic generated tests could still pull semantic verdicts in unsupported directions.

Normalized trace: `traces/trace-006-iteration-2-1/`.

---

## trajectory-007 — Advanced Iteration 2.2: evidence weighting

Human instruction: `go ahead with 2.2`.

Iteration 2.2 assigned confidence semantics to generated evidence and added a deterministic weighted-verdict gate plus stagnation stopping. The ten-case run measured 30.0% accuracy, 0.0% false acceptance, and 50.863s average runtime. Safety held, but accuracy and runtime showed that the workflow still paid too much for model reasoning when deterministic evidence already contained useful structure.

Normalized trace: `traces/trace-007-iteration-2-2/`.

---

## trajectory-008 — Advanced Iteration 2.3: deterministic test-delta engine

Human instruction: `here you go I guess it needs fixing if it does go ahead`.

Iteration 2.3 introduced deterministic comparison of original/patched pytest failure identifiers. It resolved observed partial, ineffective, and regression cases without extra verifier calls and reduced average runtime to 11.657s, but one Investigator timeout left only 9/10 cases complete and suite-repaired cases still used unnecessary semantic calls.

Normalized trace: `traces/trace-008-iteration-2-3/`.

---

## trajectory-009 — Advanced Iteration 2.4: test-first routing

Human instruction: local Iteration 2.3 outputs showed 50.0% accuracy, 0.0% false acceptance, 11.657s average runtime, and one Investigator timeout; the coding agent was asked to continue fixing the architecture.

Iteration 2.4 moved deterministic original/patched execution before any agent call. Mechanically decisive cases return without Investigator, Reproducer, or Verifier. The human verified `43 passed in 35.58s` and a clean ten-case Benchmark v1 run at 100.0% accuracy, 0.0% false acceptance, and 1.019s average runtime.

That apparent perfect result became a benchmark diagnostic rather than a final claim: all ten cases were solved without agent calls, proving Benchmark v1 exposed the oracle through its public tests.

Normalized trace: `traces/trace-009-iteration-2-4/`.

---

## trajectory-010 — Benchmark v2 oracle separation

Human instruction: `okay do it`.

The benchmark was redesigned before Challenger work. Public cases now use `case.json` with no expected verdict. Expected verdicts and hidden nearby/boundary/regression tests moved to evaluator-only material under `eval/benchmark_v2/`. The loader rejects inline oracle leakage, evaluators accept an explicit `--oracle-root`, and Benchmark v2 reports use separate artifact directories.

A reproducible builder creates ten public cases from the frozen v1 implementations with narrow reported-trigger tests. A separation audit verifies the intended public execution shapes and evaluator-only hidden behavior. Representative partial/regression cases deliberately look repaired on the public trigger while hidden tests retain the broader oracle.

Local tests, benchmark build/audit, and the first Baseline v2 run are pending. That first clean Baseline v2 result must be frozen before Challenger implementation.

Normalized trace: `traces/trace-010-benchmark-v2/`.

---

## Ongoing trace-capture rule

Every substantial coding-agent round should update both this human-readable trajectory log and a normalized package under `traces/` while the work is still fresh. Preserve exact human instructions, observable repository/tool actions, failures/retries, verification, measurable outcomes, and relevant model/provider metadata. Do not invent historical gaps, include credentials, or expose private chain-of-thought.
