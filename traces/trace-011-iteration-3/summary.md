# Iteration 3 Challenger summary

Iteration 3 adds the first explicit adversarial agent capability to `refute` on the oracle-separated Benchmark v2.

The public test-first layer remains unchanged for cheap deterministic triage. When a reported-trigger test is repaired (`suite_repaired`), the Investigator frames expected behavior and risk areas, then the Challenger proposes one to three nearby pytest falsification cases using only public issue text, code/diff, and public evidence.

Every challenge is executed deterministically on both original and patched code. A challenge that passes on original and fails on patch is classified as a regression counterexample. A challenge that fails on both original and patch after the public trigger is repaired is classified as remaining-bug evidence and supports `partial_fix`. Pytest timeouts and exit codes 2+ are explicitly invalid execution rather than semantic evidence.

The evaluator now records Challenger case yield and challenge counterexample counts. Benchmark oracles and hidden tests remain evaluator-only and are not read by the Iteration 3 verifier.

Local verification is pending.
