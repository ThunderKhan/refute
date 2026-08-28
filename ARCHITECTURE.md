# refute Architecture

## Design thesis

`refute` separates semantic reasoning from mechanical truth.

Agents decide **what should be investigated or challenged**. Deterministic runtime components establish **what actually happened**. Final verification must be constrained by persisted evidence.

## High-level flow

```text
CLI
  |
  v
Run Orchestrator
  |
  +--> Investigator Agent      (semantic reasoning)
  |
  +--> Reproducer Agent        (semantic reasoning + bounded retry)
  |        |
  |        v
  |    Runtime Executor        (deterministic)
  |
  +--> Challenger Agent        (targeted falsification)
  |        |
  |        v
  |    Runtime Executor        (deterministic)
  |
  +--> Regression Runner       (deterministic)
  |
  v
Evidence Store + Provenance
  |
  v
Verifier
  |
  v
Verdict + Report + Limitations
```

## Current architecture boundary

The Milestone 2 backbone establishes these package boundaries before the advanced agents are implemented:

```text
src/refute/
├── agents/          # semantic roles: investigator, reproducer, challenger, verifier
├── benchmark/       # case discovery and evaluation
├── evidence/        # evidence records, artifacts and provenance index
├── providers/       # model provider boundary
├── runtime/         # deterministic execution boundary
├── orchestrator.py  # verification-run state machine
├── baseline.py      # static baseline experiment
├── case.py          # benchmark case loader
├── executor.py      # current deterministic subprocess implementation
└── cli.py           # user-facing commands
```

The compatibility modules (`executor.py`, `llm.py`, etc.) remain in place while the architecture evolves, avoiding a disruptive refactor during the hackathon.

## Responsibilities

### Run orchestrator

Owns verification state and legal stage transitions. It does not decide whether a patch is correct.

Planned stages:

1. loaded
2. investigated
3. reproduction attempted
4. original verified
5. patch verified
6. challenged
7. regression checked
8. verdict ready
9. complete

### Agents

Agents are used only where semantic judgment is useful.

- **Investigator**: interpret the issue, expected behavior, likely code path and risk areas.
- **Reproducer**: synthesize an executable reproduction and revise it using execution feedback.
- **Challenger**: generate targeted nearby cases intended to falsify an apparently successful patch.
- **Verifier**: explain the evidence-constrained verdict and limitations.

The role names are architectural responsibilities, not a requirement that four separate model instances must exist.

### Runtime

The runtime is deterministic. It owns command execution, timeouts, exit status, stdout/stderr and later sandbox controls.

An LLM must never be asked to decide whether a command passed when the runtime already has the exit code.

### Evidence

Every material observation should become an `EvidenceRecord` with:

- evidence ID,
- run ID,
- case ID,
- workflow stage,
- evidence kind,
- human-readable summary,
- artifact path where applicable,
- structured metadata.

The evidence store writes an append-only `evidence.jsonl` provenance index and immutable run artifacts.

### Benchmark

The benchmark subsystem owns fair comparison between the baseline and later advanced stages.

The baseline and advanced solution must run on the same cases. Ground-truth verdicts are evaluation-only and are never passed to the model.

## Baseline

The baseline is intentionally simple but reasonable:

```text
issue report + source diff
        |
        v
single static coding-agent review
        |
        v
structured verdict
```

It performs no execution, reproduction or adversarial testing.

`refute eval-baseline benchmark` produces aggregate accuracy, false-acceptance rate, per-class accuracy, a confusion matrix and persisted evaluation reports.

## Advanced target

The advanced workflow will evolve incrementally:

```text
baseline
  -> deterministic execution
  -> investigator
  -> reproduction loop
  -> challenger
  -> regression verification
  -> evidence-constrained verifier
```

Each addition must be evaluated on the same benchmark before it is considered useful.

## Core invariant

> Agents propose and reason. Deterministic tools observe. Evidence constrains the verdict.

If the available evidence cannot support a conclusion, `refute` should return `inconclusive` rather than manufacture certainty.
