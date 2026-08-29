# Trace 009 — Iteration 2.4 test-first routing

Objective: prevent provider latency or failure from blocking cases that deterministic execution can already resolve, and avoid unnecessary semantic calls on suite-repaired cases.

Implementation changes:
- allow test-first orchestration transitions;
- add `verify_v24.py`;
- run original and patched suites before any agent call;
- reuse the deterministic pytest failure-delta engine;
- resolve partial, ineffective, regression, suite-repaired, and both-pass outcomes mechanically when supported;
- invoke Investigator/Reproducer/Verifier only for genuinely ambiguous deltas;
- add tests proving deterministic routes do not call the LLM;
- expose `--iteration 2.4` and separate evaluation artifacts.

Important interpretation rule: `complete_fix` from suite repair is scoped to the observed suite. It is not a claim of global correctness. If the current benchmark becomes nearly deterministic, the benchmark must be redesigned with hidden oracle coverage before Challenger work.
