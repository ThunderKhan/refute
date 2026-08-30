# refute Architecture

## Design thesis

`refute` separates semantic prioritization from mechanical truth.

> **Agents prioritize. Deterministic tools observe. Evidence constrains the verdict.**

The final system deliberately narrows the language model's responsibility. The model does not decide whether a command passed, does not author arbitrary executable assertions in the frozen Iteration 5 path, and does not directly choose the final verdict.

## Frozen Benchmark v2 architecture

```text
public issue contract + original/patched fixture
                    |
                    v
             public pytest run
                    |
                    v
           deterministic test delta
                    |
        +-----------+-----------+
        |                       |
        | repaired trigger      | other evidence shape
        v                       v
 deterministic public-      deterministic
 contract probe compiler    test-first triage
        |
        v
 bounded valid probe pool
        |
        v
 agent prioritizes probe IDs
        |
        v
 deterministic probe execution
 on original + patched code
        |
        v
 deterministic evidence policy
        |
        v
 five-way verdict + evidence store
```

### Why this boundary exists

Iterations 3.x and 4 progressively reduced model freedom but still asked the model to invent executable or semantic assertions. Accuracy remained around 30% on Benchmark v2. Iteration 5 moved mechanically recognizable requirements into deterministic compilation and left the model only bounded prioritization. That structural change produced the frozen 10/10 Benchmark v2 result.

## Real GitHub PR product path

The developer-facing path adds repository ingestion and reproduction around the same evidence-first core.

```text
public GitHub PR URL
        |
        v
PR inspection + base/head SHAs + public contract
        |
        v
isolated per-run workspace + Python environment
        |
        v
changed pytest tests detected?
   | yes                    | no
   v                        v
copy patch-authored         full-suite fallback
changed tests onto base
   |
   v
same reproduction on base + patch
   |
   v
reported trigger repaired?
   |
   v
try deterministic contract probes
   |
   +--> probes available -> agent prioritizes valid probe IDs
   |
   +--> no probes -> bounded nearby existing-test candidate ranking
                         |
                         v
                  agent prioritizes candidates
                         |
                         v
                  deterministic execution
                         |
                         v
                evidence-backed verdict
```

The nearby-test adversary may discover a concrete regression when an existing test passes on base and fails on patch. Surviving nearby tests increase confidence but do not by themselves prove completeness, so a run may remain `inconclusive`.

## Product surfaces

All user surfaces call the same Python verification machinery.

```text
CLI ---------------------+
                         |
React/Vite dashboard --> local dashboard API --> verification engine
                         |
MCP stdio server --------+
```

### CLI

Reproducible benchmark and local-case interface.

### Dashboard

Human-facing workflow with two modes:

- controlled Benchmark v2 cases;
- compatible public GitHub Python/pytest PRs.

The dashboard renders the public PR contract, execution/reproduction timeline, probes or nearby-test evidence, and final verdict.

### MCP

`src/refute/mcp_server.py` exposes the same real-PR workflow to coding-agent hosts over local stdio MCP.

Tools:

```text
inspect_pr          read-only PR inspection
verify_pr           starts async verification after explicit human approval
get_verify_job      polls long-running verification
get_run             reads persisted evidence without re-execution
```

`verify_pr` is asynchronous because dependency provisioning and repository tests can take minutes while many MCP clients impose much shorter request timeouts.

## Major components

```text
src/refute/
├── agents/
│   ├── probe_compiler_v5.py     deterministic public-contract -> probe compiler
│   └── probe_planner_v5.py      bounded model prioritization of valid probe IDs
├── benchmark/                   evaluation and oracle-loading boundary
├── evidence/                    append-only evidence/provenance records
├── cli.py                       command-line surface
├── dashboard_server.py          local dashboard API + async live-run jobs
├── github_pr.py                 public PR inspection, revisions, env/reproduction setup
├── real_repo_adversary.py       bounded existing-test candidate ranking/planning/execution
├── mcp_server.py                stdio MCP tools + async verification jobs
├── executor.py                  deterministic subprocess execution
├── orchestrator.py              run state machine
└── verify_v5.py                 frozen Iteration 5 benchmark verifier

frontend/                        React/Vite dashboard
benchmark_v2/                    public oracle-free controlled cases
eval/benchmark_v2/               evaluator-only verdicts + hidden checks
traces/                          normalized coding-agent development trajectories
```

## Evidence model

Every material runtime observation should be persisted with:

- run ID;
- case ID;
- workflow stage;
- evidence kind;
- summary;
- artifact path where applicable;
- structured metadata.

Per-run evidence lives under:

```text
artifacts/runs/<run_id>/
```

The evidence store maintains an append-only `evidence.jsonl` provenance index. Product integrations may add structured sidecar files such as `nearby_adversary.json` or `mcp_result.json`, but those do not replace the underlying deterministic test evidence.

## Verdict semantics

The final output is one of:

```text
complete_fix
partial_fix
ineffective_fix
regression_introduced
inconclusive
```

A stronger verdict requires stronger observed evidence. `inconclusive` is not an error state; it is the required outcome when the evidence does not justify certainty.

## Benchmark integrity boundary

Benchmark v2 public cases contain no expected verdict. Evaluator-only material lives under `eval/benchmark_v2/` and is loaded only after a verdict exists for scoring.

The frozen Iteration 5 verifier must not read:

```text
eval/benchmark_v2/oracles.json
eval/benchmark_v2/hidden_tests.json
```

The real GitHub PR product path is separate from the Benchmark v2 metric and must not be presented as evidence for the 10/10 benchmark score.

## Safety boundary

The GitHub workflow can install declared dependencies and execute third-party pytest code. Current safeguards are:

- public PRs only;
- explicit human approval before execution;
- isolated per-run Python environment;
- bounded execution timeouts;
- no automatic merge/deploy action;
- deterministic evidence collection.

The per-run Python environment is **not** strong OS/container sandboxing. The current hackathon product therefore does not claim safe execution of arbitrary untrusted repositories.

## Core invariant

If a fact is mechanically observable, an agent should not be responsible for inventing it.

If the available evidence cannot support a conclusion, `refute` returns `inconclusive` rather than manufacturing certainty.
