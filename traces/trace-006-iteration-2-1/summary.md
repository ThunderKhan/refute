# Iteration 2.1 — discriminating reproduction semantics

Iteration 2.1 corrects the central semantic error discovered in Iteration 2.

Previously, any generated test that failed on the original implementation was labeled a successful reproduction, even if the same generated test also failed on the patched implementation. That conflated "the test failed" with "the test specifically demonstrates the reported bug."

Iteration 2.1 now requires a generated test to discriminate between versions:

- original FAIL + patch PASS -> discriminating reproduction; accept as reproduction evidence,
- original FAIL + patch FAIL/timeout -> non-discriminating; feed both execution outputs back and retry,
- original PASS/timeout -> not reproduced; feed original execution output back and retry.

The previous Iteration 2 implementation remains available so the negative experiment stays reproducible. Iteration 2.1 writes evaluation artifacts under `artifacts/eval/advanced_iteration_2_1/` rather than overwriting Iteration 2.

No Challenger behavior was added in this round. The purpose is to repair evidence semantics before increasing system capability.
