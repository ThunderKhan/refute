# Trace Summary — Static-review baseline

## Objective

Create a fair, intentionally limited baseline that judges patches from issue text and a static diff only.

## Engineering result

The coding agent added provider abstraction, static diff generation, a strict no-execution review prompt, structured five-class verdict parsing, artifact persistence, CLI integration, and fake-model tests.

## Important design constraint

Ground-truth expected verdicts are not included in the model prompt. The baseline cannot execute code, reproduce bugs, or generate tests. This limitation is deliberate so later workflow improvements can be attributed to added capabilities rather than hidden oracle access.

## Human verification

The local suite reported `12 passed in 3.33s`. Running `qwen3:0.6b` on the three seed cases produced 0/3 correct verdicts. Those results motivated building a larger batch evaluator rather than drawing conclusions from three examples.

## Reproducible diff

Repository changes for this trace are represented by Git commit range `d099e74..7b83be2`.
