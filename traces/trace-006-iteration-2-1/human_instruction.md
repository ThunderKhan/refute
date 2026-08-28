# Human instruction

> "Start with 2.1 and fix the errors"

Context: Advanced Iteration 2 produced a clean ten-case run but regressed to 10.0% verdict accuracy. The key semantic flaw was that a generated test failing on both original and patched code was being treated as a successful reproduction. The human requested a focused correction before adding the Challenger.
