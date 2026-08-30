# Post-freeze Holdout v1 protocol

This experiment exists to test whether the frozen Iteration 5 result generalizes beyond the ten Benchmark v2 cases used during development.

## Why this exists

Benchmark v2 is oracle-separated, but the system designer still observed failures on those ten cases while iterating. Oracle separation prevents the verifier from reading the answers; it does not by itself eliminate development-set overfitting.

Holdout v1 therefore follows a stricter protocol:

1. Iteration 5 verification semantics were frozen first.
2. The no-agent deterministic-order ablation was added without modifying the verifier.
3. The ablation result was observed and recorded.
4. Holdout v1 was then authored as a new post-freeze case set.
5. The holdout builder and audit were committed before any Iteration 5 or ablation result on Holdout v1 was observed.
6. After results are observed, `verify_v5.py`, `probe_compiler_v5.py`, `probe_planner_v5.py`, classification logic, and verdict thresholds must not be changed in response to Holdout v1.
7. Whatever result occurs is reported.

This is a post-freeze holdout, not a claim of independently curated third-party data. The cases were authored within the stated MVP contract domain while changing functions, constants, implementations, and combinations of requirements.

## Frozen verifier reference

The pre-ablation Iteration 5 verifier reference is:

```text
f84395403f5d2af59ee1b8d6170ef2c77a4fb577
```

The later commits add evaluation/documentation infrastructure only; the holdout protocol forbids benchmark-driven verifier tuning.

## Public holdout freeze

The first build/audit was performed from repository commit:

```text
211591da45fe0fea1e34a37414d6291245e1b7ff
```

The public Holdout v1 digest was recorded before evaluation:

```text
c2604717e69fb99c2d30e17ee4f586d4463e3bd032e55344684e9db9992b5cb1
```

The audit reported:

```text
cases: 12
evaluator oracles: 12
AUDIT PASSED: holdout public material contains no verdict oracle and case/oracle sets match.
```

Public `case.json` files do not contain expected verdicts; evaluator-only answers live under:

```text
eval/holdout_v1/oracles.json
```

## Evaluation order

The planned order was:

```powershell
refute eval-baseline holdout_v1 --oracle-root eval\holdout_v1 --provider ollama --model qwen3:0.6b --llm-timeout 30

python scripts/eval_probe_order_ablation.py holdout_v1 --oracle-root eval\holdout_v1 --probe-budget 2

refute eval-advanced holdout_v1 --oracle-root eval\holdout_v1 --provider ollama --model qwen3:0.6b --iteration 5 --llm-timeout 30
```

The first baseline attempt failed before producing benchmark results because the local model provider timed out. This is recorded as an execution failure, not converted into a score. The deterministic-order and frozen Iteration 5 evaluations then completed without code changes.

A single later baseline retry was allowed only to distinguish a transient provider failure from a reproducible evaluation result. `ollama list` confirmed `qwen3:0.6b` was installed, but the retry again failed with `could not reach language-model provider: timed out` before producing any case-level score. No further baseline retries are part of this protocol. Holdout v1 therefore has **no static-baseline accuracy result**; the absence is reported as a repeated local provider timeout rather than imputed, discarded, or retried until successful.

## First observed Holdout v1 results

### Static baseline

- first attempt: provider timeout before benchmark result
- one permitted retry: provider timeout before benchmark result
- model installation check: `qwen3:0.6b` present locally
- reported accuracy: **unavailable**
- interpretation: execution/provider failure, not a scored benchmark outcome

### Deterministic-order ablation, no model planner

- cases: **12/12**
- verdict accuracy: **83.3%**
- false acceptance rate: **20.0%**
- challenge counterexamples: **6**
- average runtime: **2.698s/case**
- wrong cases: `holdout_010`, `holdout_012`
- both wrong cases were predicted `complete_fix`

### Frozen Iteration 5 with model planner

- completed cases: **12/12**
- errors: **0**
- verdict accuracy: **83.3%**
- false acceptance rate: **20.0%**
- Challenger case yield: **60.0%**
- challenge counterexamples: **6**
- challenge generation/planner failures recorded: **2**
- planner fallback cases: **2**
- average runtime: **9.989s/case**
- wrong cases: `holdout_010`, `holdout_012`
- both wrong cases were predicted `complete_fix`

### Immediate interpretation

The holdout demonstrates a real generalization gap relative to the 10/10 development benchmark: frozen Iteration 5 drops from **100.0% to 83.3% accuracy**, with FAR rising from **0.0% to 20.0%** on this 12-case post-freeze set.

The model planner did **not** improve verdict accuracy over deterministic probe order under the same two-probe budget. Both systems found the same six counterexamples and missed the same two cases. The planner path was also materially slower and experienced two provider/planner failures that required deterministic fallback.

Therefore the correct component-level claim is narrower than the original architectural hypothesis:

> Within this contract domain, the deterministic contract compiler is the primary source of verification value; model-based probe prioritization has not shown measurable verdict improvement in either Benchmark v2 or Holdout v1 under the tested budget.

This is not grounds for verifier tuning. The frozen result is preserved as observed.

## Interpretation rules

No target score is required.

- If Iteration 5 retains a large improvement over the static baseline, that is evidence of post-freeze generalization within the stated MVP domain.
- If deterministic ordering matches Iteration 5 again, do not claim that planner prioritization improves accuracy.
- If Iteration 5 beats deterministic ordering under the same probe budget, that is evidence for planner value under bounded execution.
- If accuracy drops materially, report the drop and use it to narrow the generalization claim.
- Do not edit the verifier and rerun until the result looks better.

A lower but genuinely post-freeze result is more informative than a tuned 100% score.
