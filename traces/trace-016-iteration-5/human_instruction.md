# Human checkpoint

The human supplied a clean Iteration 4 local run showing 67 passing tests and a Benchmark v2 result of 30.0% accuracy, 0.0% FAR, 14.3% Challenger yield, one counterexample, nine generation failures, and 13.026s average runtime.

The observed plateau triggered a structural redesign: stop asking the small model to invent assertions and instead compile a bounded probe pool deterministically from the public issue contract, leaving the agent to prioritize probe IDs.
