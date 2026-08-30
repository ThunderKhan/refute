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

The default probe budget is `2`, matching the final Benchmark v2 Iteration 5 evaluation.

## Run

From the repository root after building Benchmark v2:

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

## Interpretation

This is a component ablation, not a new optimized iteration.

- If deterministic ordering matches Iteration 5, the correct conclusion is that agent prioritization was not necessary on this benchmark under this budget.
- If Iteration 5 outperforms deterministic ordering, the difference is evidence that bounded semantic prioritization contributes under the same compiled probe pool and execution budget.
- Either outcome must be reported. The verifier must not be modified in response to the ablation result.

The frozen Iteration 5 headline result remains a separate historical measurement. This ablation is intended to clarify **which component produced that result**, not to replace or tune it.
