# Trace 010 — Benchmark v2 oracle separation

## Objective

Repair the benchmark after Iteration 2.4 deterministically saturated Benchmark v1 without invoking agents.

## Observable changes

- made `VerificationCase.expected_verdict` optional;
- taught `load_case` to accept public `case.json` and reject inline `expected_verdict` leakage;
- added evaluator-only oracle loading;
- updated baseline and advanced evaluators to accept an oracle root and keep Benchmark v2 artifacts separate;
- added CLI `--oracle-root` support;
- added a reproducible ten-case public benchmark builder;
- added evaluator-only verdict oracles and hidden nearby/boundary/regression tests;
- added tests for oracle-free public cases and oracle resolution;
- documented the public/evaluator boundary and updated the improvement changelog.

## Design invariant

Verification agents operate on the public case only. Expected verdicts and hidden tests are evaluation material and must never be passed to Investigator, Reproducer, Verifier, or future Challenger prompts.

## Decision

Freeze the first clean Baseline v2 measurement before any Challenger implementation or prompt tuning.
