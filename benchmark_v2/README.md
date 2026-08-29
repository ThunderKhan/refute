# Benchmark v2 — public cases only

Benchmark v2 separates what `refute` is allowed to see from what the evaluator uses to score it.

Each generated public case contains:

```text
case_XXX/
  case.json       # case ID + public test command; NO expected verdict
  issue.md
  original/
    app.py
    test_app.py   # public reported-bug test only
  patched/
    app.py
    test_app.py   # same public test
```

Evaluator-only material lives outside this tree under `eval/benchmark_v2/`:

- `oracles.json` — expected verdicts used only for scoring.
- `hidden_tests.json` — nearby/boundary/regression cases withheld from agents and public execution.

Regenerate all ten public cases from the frozen v1 source implementations with:

```powershell
python scripts/build_benchmark_v2.py
```

The builder intentionally narrows the public tests. Partial-fix and regression cases can therefore look repaired on the reported trigger while evaluator-only tests retain the broader ground truth. This prevents the deterministic test-delta engine from reading the answer directly from the public suite.

Do not put `expected_verdict`, hidden tests, or evaluator notes inside a public case directory.
