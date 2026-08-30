# Post-freeze Holdout v1 protocol

This experiment exists to test whether the frozen Iteration 5 result generalizes beyond the ten Benchmark v2 cases used during development.

## Why this exists

Benchmark v2 is oracle-separated, but the system designer still observed failures on those ten cases while iterating. Oracle separation prevents the verifier from reading the answers; it does not by itself eliminate development-set overfitting.

Holdout v1 therefore follows a stricter protocol:

1. Iteration 5 verification semantics were frozen first.
2. The no-agent deterministic-order ablation was added without modifying the verifier.
3. The ablation result was observed and recorded.
4. Holdout v1 was then authored as a new post-freeze case set.
5. The holdout builder and audit are committed before any Iteration 5 or ablation result on Holdout v1 is observed.
6. After results are observed, `verify_v5.py`, `probe_compiler_v5.py`, `probe_planner_v5.py`, classification logic, and verdict thresholds must not be changed in response to Holdout v1.
7. Whatever result occurs is reported.

This is a post-freeze holdout, not a claim of independently curated third-party data. The cases were authored within the stated MVP contract domain while changing functions, constants, implementations, and combinations of requirements.

## Frozen verifier reference

The pre-ablation Iteration 5 verifier reference is:

```text
f84395403f5d2af59ee1b8d6170ef2c77a4fb577
```

The later commits add evaluation/documentation infrastructure only; the holdout protocol forbids benchmark-driven verifier tuning.

## Build and freeze the public set

```powershell
python scripts/build_holdout_v1.py
python scripts/audit_holdout_v1.py
```

The builder prints a SHA-256 digest over every public Holdout v1 file. Record that digest before evaluation. Public `case.json` files do not contain expected verdicts; evaluator-only answers live under:

```text
eval/holdout_v1/oracles.json
```

## Evaluation order

Run these without editing the verifier between commands:

```powershell
refute eval-baseline holdout_v1 --oracle-root eval\holdout_v1 --provider ollama --model qwen3:0.6b --llm-timeout 30

python scripts/eval_probe_order_ablation.py holdout_v1 --oracle-root eval\holdout_v1 --probe-budget 2

refute eval-advanced holdout_v1 --oracle-root eval\holdout_v1 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

This yields three directly comparable views:

- static LLM baseline;
- deterministic contract probes with no model planner;
- frozen Iteration 5 with bounded model probe prioritization.

## Interpretation rules

No target score is required.

- If Iteration 5 retains a large improvement over the static baseline, that is evidence of post-freeze generalization within the stated MVP domain.
- If deterministic ordering matches Iteration 5 again, do not claim that planner prioritization improves accuracy.
- If Iteration 5 beats deterministic ordering under the same probe budget, that is evidence for planner value under bounded execution.
- If accuracy drops materially, report the drop and use it to narrow the generalization claim.
- Do not edit the verifier and rerun until the result looks better.

A lower but genuinely post-freeze result is more informative than a tuned 100% score.
