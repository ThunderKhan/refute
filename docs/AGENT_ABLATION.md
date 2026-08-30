# Iteration 5 agent-prioritization ablation

This experiment answers a specific adversarial question about the final `refute` architecture:

> Does the bounded LLM probe planner contribute anything, or does the deterministic contract compiler alone explain the Iteration 5 result?

## Frozen system

The final Iteration 5 verifier was frozen before this ablation harness was added. The reference pre-ablation repository commit is:

```text
f84395403f5d2af59ee1b8d6170ef2c77a4fb577
```

The ablation does **not** modify `verify_v5.py`, the deterministic contract compiler, probe definitions, classification rules, or verdict thresholds.

## Controlled change

Iteration 5 normally uses:

```text
public contract
    -> deterministic compiler
    -> bounded probe pool
    -> LLM planner chooses up to N probe IDs
    -> deterministic execution
    -> evidence-constrained verdict
```

The ablation changes exactly one responsibility:

```text
public contract
    -> deterministic compiler
    -> bounded probe pool
    -> first N probes in deterministic compiler order
    -> deterministic execution
    -> same evidence-constrained verdict semantics
```

No LLM/provider is instantiated by the ablation evaluator.

The probe budget is `2`, matching the final Benchmark v2 Iteration 5 evaluation.

## Run

```powershell
python scripts/eval_probe_order_ablation.py benchmark_v2 --oracle-root eval\benchmark_v2 --probe-budget 2
```

Results are written to:

```text
artifacts/eval/iteration_5_probe_order_ablation/
  summary.json
  cases.jsonl
  report.md
```

## Observed result

The ablation was run after the verifier freeze. It matched Iteration 5 on every Benchmark v2 case:

```text
cases: 10
probe budget: 2
verdict accuracy: 100.0%
false acceptance rate: 0.0%
challenge counterexamples: 4
average runtime: 2.043s
```

All ten verdicts matched the Benchmark v2 oracle, including the same four counterexample-producing cases. No model/provider was used.

## Interpretation

The correct conclusion is deliberately narrow:

> **On Benchmark v2, with a probe budget of two, LLM probe prioritization was not necessary for the final 100% verdict accuracy. The deterministic contract compiler plus deterministic probe order was sufficient.**

This does **not** invalidate the Iteration 5 architecture, but it changes the attribution of the measured improvement. The benchmark evidence supports the deterministic responsibility-boundary change much more strongly than it supports a claim that semantic probe prioritization improved accuracy.

The planner remains part of the product architecture for situations where a bounded probe pool contains more candidate checks than the execution budget can cover, but Benchmark v2 does not demonstrate a measurable planner advantage.

This negative/null ablation result is preserved rather than hidden. The next validation step is a post-freeze holdout: new cases are frozen before running the unchanged verifier and the same deterministic-order ablation against them.
