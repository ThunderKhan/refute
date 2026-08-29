# Benchmark v2 evaluator-only material

This directory is outside the public `benchmark_v2/` case tree on purpose.

`oracles.json` contains the expected verdict for scoring. `hidden_tests.json` contains nearby, boundary, and regression tests that are withheld from the verification agents and from each case's public test command.

The evaluator may read `oracles.json`; the verification pipeline must not. A public `case.json` containing `expected_verdict` is rejected by the loader.

For the frozen Baseline v2 run, use:

```powershell
python scripts/build_benchmark_v2.py
refute eval-baseline benchmark_v2 --oracle-root eval\benchmark_v2 --provider ollama --model qwen3:0.6b --llm-timeout 30
```

For later advanced comparisons, use the same public cases and the same oracle root. Do not compare an advanced Benchmark v2 result against Baseline v1, because the case evidence changed.
