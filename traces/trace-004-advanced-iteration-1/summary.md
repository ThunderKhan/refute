# Summary

Advanced Iteration 1 introduces the first real advanced verification path in `refute` without yet adding generated reproduction or Challenger behavior.

The Investigator performs semantic issue understanding and emits a structured verification hypothesis. The deterministic executor then runs the benchmark's existing test command against the original and patched trees. Every observation is recorded through the evidence store. A final verifier receives the structured hypothesis plus explicit execution facts and must return one of the five project verdict classes while acknowledging that this iteration has not generated new tests.

This round also adds one-command advanced benchmark evaluation so the exact same ten-case benchmark can be compared against the frozen static Baseline v1.

The main experimental question is whether structured investigation plus real runtime evidence improves verdict accuracy and reduces false acceptance relative to the static baseline.

Local verification and the first measured advanced result are intentionally left pending rather than inferred.
