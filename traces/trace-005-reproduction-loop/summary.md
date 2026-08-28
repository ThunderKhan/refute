# Trace 005 — Reproduction loop

Advanced Iteration 2 adds the first explicit agent/tool feedback loop to `refute`.

The Investigator still produces the semantic bug hypothesis. The new Reproducer then generates a focused pytest test intended to fail on the original implementation and pass when the reported bug is correctly fixed. Each generated test is validated before execution, run against the original first, and retried with execution feedback when it fails to reproduce the bug. Once a candidate reproduces the original failure, the exact same test is executed against the patched implementation.

All generated test source and execution results are persisted as evidence. Existing test-suite evidence is still collected. The final verifier receives both categories of evidence but no Challenger-generated nearby cases yet.

Advanced Iteration 1 remains selectable so the measured contribution of reproduction can be evaluated independently rather than replacing the previous experiment.

Local verification and benchmark results are still pending.
