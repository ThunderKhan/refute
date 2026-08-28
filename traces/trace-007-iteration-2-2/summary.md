# Iteration 2.2 summary

Iteration 2.2 addresses the evidence-weighting flaw exposed by the clean Iteration 2.1 run.

The new verifier treats only an original-FAIL/patch-PASS generated test as high-confidence reproduction evidence. A generated test that fails on both versions is explicitly diagnostic-only and cannot, by itself, justify `partial_fix`, `ineffective_fix`, or `regression_introduced` when the patched deterministic suite passes. A generated test that passes or times out on the original is treated as not reproduced and contributes no negative evidence against the patch.

A deterministic weighted-verdict gate enforces those rules even when the model ignores them. Iteration 2.2 also stops the Reproducer early after two consecutive non-discriminating attempts, reducing wasted model calls when the tiny local model is clearly not converging.

Iteration 2.1 remains available unchanged for ablation comparison. Iteration 2.2 has separate CLI/evaluator routing and separate evaluation artifacts.

Local verification and benchmark results are intentionally left pending until observed on the user's machine.
