# Iteration 5 trace summary

## Goal

Break the 30% accuracy plateau without returning to unsafe static approval or unconstrained model-authored executable assertions.

## Structural change

Iteration 5 moved semantic probe construction into a deterministic compiler for a deliberately small public issue-contract vocabulary. The language model receives only valid probe IDs/descriptions and prioritizes a bounded subset. Deterministic tools execute the selected probes against original and patched code; deterministic policy maps the observed evidence to the final verdict.

## Why this round mattered

Prompt-heavy Iterations 3.1 through 4 remained around 30% accuracy. The decisive improvement came from changing the responsibility boundary rather than elaborating the prompt.

> Agents prioritize. Deterministic tools observe. Evidence constrains the verdict.

## Human verification

The frozen local verification transcript in `verification.txt` records:

- 72 passing project tests at the Iteration 5 measurement point;
- 10/10 correct Benchmark v2 verdicts;
- 0.0% false acceptance rate;
- 57.1% Challenger case yield;
- 4 executable counterexamples;
- 0 challenge-generation failures;
- 0 planner fallbacks;
- 5.077s average runtime per case.

The benchmark is oracle-separated: evaluator-only expected verdicts and hidden tests are not inputs to the verifier.

## Claim boundary

This trace supports the measured result only on the controlled ten-case Benchmark v2. It does not establish universal patch-verification accuracy.

## Trace integrity

`actions.jsonl` contains normalized observable events only. It does not reconstruct or expose hidden chain-of-thought.
