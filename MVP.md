# MVP.md

# refute — Minimum Viable Product

## 1. MVP Objective

Build the smallest version of `refute` that can demonstrate the central hypothesis:

> **Executable verification helps an agent classify bug-fix patches more reliably than static review alone.**

The MVP should be narrow, measurable, and fully reproducible.

---

## 2. Scope

### Supported
- Python
- pytest
- local benchmark fixtures
- issue text supplied as Markdown or plain text
- original and patched code supplied as separate fixture directories
- deterministic test execution
- agent-generated reproduction tests
- agent-generated nearby/adversarial tests
- evidence-backed verdicts

### Explicitly Not Supported
- arbitrary GitHub repositories
- arbitrary languages
- Docker orchestration unless needed later
- remote patch fetching
- auto-merging
- auto-committing
- production code execution
- security guarantees
- full formal verification
- universal build-system detection

---

## 3. MVP User Story

> As a maintainer, I want to give `refute` a bug report and proposed patch so that I can see whether the patch actually resolves the reported defect and whether nearby failures remain.

---

## 4. MVP Demo Story

The strongest demo case should look like this:

### Bug report
A function fails on a boundary or special input.

### Proposed patch
The patch handles the exact reported input but does not correctly solve the broader condition.

### Existing tests
All pass.

### Baseline
Static agent review says the patch is correct.

### `refute`
1. reproduces the original bug,
2. confirms the reported example passes after the patch,
3. generates a nearby boundary case,
4. discovers the related failure,
5. returns:

```text
VERDICT: partial_fix
```

This is the core “aha” moment.

---

## 5. MVP Architecture

```text
case loader
    ↓
issue interpreter
    ↓
repository inspector
    ↓
reproduction generator
    ↓
executor
    ↓
patched/original comparator
    ↓
challenger
    ↓
regression runner
    ↓
verdict generator
    ↓
report + artifacts
```

Keep orchestration simple.

Do not add more agents unless a measured experiment shows value.

---

## 6. Suggested Repository Layout

```text
refute/
├── README.md
├── PROBLEM_STATEMENT.md
├── PRD.md
├── MVP.md
├── REPRODUCTION.md
├── TRAJECTORIES.md
├── pyproject.toml
├── requirements.txt
├── src/
│   └── refute/
│       ├── __init__.py
│       ├── cli.py
│       ├── case.py
│       ├── baseline.py
│       ├── investigator.py
│       ├── executor.py
│       ├── challenger.py
│       ├── verifier.py
│       ├── report.py
│       └── models.py
├── benchmark/
│   ├── case_001/
│   │   ├── issue.md
│   │   ├── original/
│   │   ├── patched/
│   │   └── expected.json
│   └── ...
├── eval/
│   ├── run_eval.py
│   └── metrics.py
├── artifacts/
└── tests/
```

This structure may be simplified if implementation speed demands it.

---

## 7. Benchmark Case Format

Each case directory should contain:

```text
case_001/
├── issue.md
├── original/
├── patched/
└── expected.json
```

Example `expected.json`:

```json
{
  "case_id": "case_001",
  "expected_verdict": "partial_fix",
  "test_command": "pytest -q",
  "notes": "Patch fixes the reported input but misses the adjacent boundary."
}
```

Optional:

```text
oracle/
hints.json
metadata.json
```

Do not expose hidden oracle information to the agent if it would leak the expected verdict.

---

## 8. MVP Baseline

### Input
- issue text
- patch diff or original/patched comparison
- limited repository context

### Process
One direct coding-agent review.

### Output

```json
{
  "case_id": "case_001",
  "verdict": "complete_fix",
  "reasoning_summary": "..."
}
```

The baseline should not execute code.

---

## 9. MVP Advanced Flow

### Stage 1 — Interpret
Extract:

```text
expected behavior
actual behavior
trigger condition
relevant uncertainty
```

### Stage 2 — Inspect
Find:

```text
likely implementation files
related tests
test command
```

### Stage 3 — Reproduce
Generate one executable test or script designed to reproduce the issue.

### Stage 4 — Execute Original
Run reproduction against original code.

Record:

```text
exit status
stdout
stderr
test result
```

### Stage 5 — Execute Patched
Run the exact same reproduction against patched code.

### Stage 6 — Challenge
Generate a small number of nearby cases.

MVP target:

**1–3 adversarial cases per benchmark case**

Potential strategies:
- boundary value
- empty value
- adjacent value
- repeated operation
- alternate valid type
- malformed variant
- state transition around the reported failure

The challenger must derive these from the reported defect rather than blindly fuzzing everything.

### Stage 7 — Regression
Run the fixture's existing pytest suite.

### Stage 8 — Verdict
Use only the collected evidence to classify the patch.

---

## 10. MVP Verdict Rules

The verifier may use deterministic evidence rules around the agent output.

Illustrative logic:

### `complete_fix`
- original defect successfully reproduced
- same reproduction passes after patch
- existing tests pass
- generated relevant adversarial cases pass

### `partial_fix`
- reported reproduction passes after patch
- at least one closely related adversarial case fails

### `ineffective_fix`
- original reproduction still fails after patch

### `regression_introduced`
- original issue is resolved
- but an existing relevant regression test fails after patch

### `inconclusive`
- original defect cannot be reproduced
- execution fails for unrelated environment reasons
- evidence conflicts
- or the system cannot establish sufficient confidence

These rules may evolve based on benchmark findings.

---

## 11. Evaluation Plan

### Target
At least 10 benchmark cases.

### Case distribution example

| Type | Cases |
|---|---:|
| Complete fix | 2 |
| Partial fix | 3 |
| Ineffective fix | 2 |
| Regression introduced | 2 |
| Challenging/inconclusive | 1 |

This is only a starting distribution.

---

## 12. Metrics

### Primary
**Verdict Accuracy**

### Secondary
- false acceptance rate
- reproduction success rate
- regression detection rate
- adversarial discovery rate
- average runtime
- average cost per case

### Example final table

| Metric | Baseline | refute | Change |
|---|---:|---:|---:|
| Verdict accuracy | TBD | TBD | TBD |
| False acceptance rate | TBD | TBD | TBD |
| Reproduction success | N/A | TBD | — |
| Regression detection | N/A | TBD | — |
| Avg runtime | TBD | TBD | TBD |
| Avg cost | TBD | TBD | TBD |

Do not invent results before evaluation.

---

## 13. MVP Milestones

### M0 — Scaffold
- repository structure
- CLI shell
- case format
- result models
- documentation skeleton
- trajectory logging decision

### M1 — Benchmark
- create first 3 cases
- deterministic ground truth
- original/patched fixture execution works

### M2 — Baseline
- one-prompt static reviewer
- structured verdict
- baseline results stored

### M3 — Reproduction Loop
- issue interpretation
- reproduction generation
- original execution
- patched execution
- evidence storage

### M4 — Challenger
- generate 1–3 nearby cases
- execute them
- detect partial fixes

### M5 — Regression + Verdict
- existing suite execution
- final verdict logic
- structured report

### M6 — Evaluation
- expand benchmark toward 10+ cases
- baseline vs advanced metrics
- challenging case analysis

### M7 — Documentation
- Improvement Changelog
- Reproduction Guide
- README framing
- failure mode
- final hot take

### M8 — Submission
- final trajectories
- clean environment test
- demo recording
- final artifact audit

---

## 14. MVP CLI

Proposed commands:

```bash
refute baseline benchmark/case_001
refute verify benchmark/case_001
refute eval benchmark/
```

Possible output:

```text
$ refute verify benchmark/case_004

refute 0.1

case: case_004
issue: parser crashes on trailing empty field

original reproduction ........ FAILS as expected
patched reproduction ......... PASSES
existing tests ............... PASSED
adversarial cases ............ 1/3 FAILED

VERDICT: partial_fix

evidence:
  artifacts/case_004/reproduction.py
  artifacts/case_004/adversarial_02.py
  artifacts/case_004/original.txt
  artifacts/case_004/patched.txt

reason:
  The patch resolves the reported example but does not correctly
  handle the adjacent two-empty-field case.
```

---

## 15. Experiment Plan

The project should evolve experimentally.

### Experiment A — Static Baseline
Question:
How accurate is one-pass static review?

### Experiment B — Add Existing Test Execution
Question:
Does simply running existing tests materially improve verdict accuracy?

### Experiment C — Add Reproduction Synthesis
Question:
Does constructing a bug-specific reproduction catch patches missed by the existing suite?

### Experiment D — Add Challenger
Question:
Do generated nearby cases reduce false acceptance of partial fixes?

### Experiment E — Candidate Removed Experiment
Possible examples:
- second independent reviewer agent
- majority vote
- excessive test generation
- repository-wide context retrieval
- long chain-of-thought style self-reflection

At least one attempted experiment should be removed if the evidence shows it adds cost/complexity without improving the outcome.

---

## 16. Agent Trajectory Requirements

From the first meaningful agent run, preserve:

- agent instructions
- prompts
- tool calls
- command outputs
- retries
- failures
- human checkpoints
- final results

Do not reconstruct trajectories at the end.

Representative trajectories for every agent/stage used must be easy for judges to follow.

---

## 17. Reproducibility Definition

The MVP is not complete until another person can start from a clean environment and run:

```bash
# install
...

# baseline
...

# advanced
...

# evaluation
...
```

and obtain the main comparison result.

---

## 18. Main MVP Risks

### Risk 1: Arbitrary repository complexity
Mitigation:
Use controlled Python fixtures.

### Risk 2: Agent-generated tests are invalid
Mitigation:
Validate syntax, run in sandbox, record failures, retry with bounded attempts.

### Risk 3: Agent sees ground-truth answer
Mitigation:
Keep expected verdict/oracle outside the context passed to the model.

### Risk 4: False confidence
Mitigation:
Support `inconclusive`.

### Risk 5: Overbuilding orchestration
Mitigation:
Start with the smallest working workflow and add components only when evaluation justifies them.

### Risk 6: Weak benchmark
Mitigation:
Design cases around specific failure classes, not cosmetic code mutations.

---

## 19. Definition of Done

The MVP is done when all of the following are true:

- [ ] `refute baseline` works
- [ ] `refute verify` works
- [ ] `refute eval` works
- [ ] original and patched versions are compared on identical reproductions
- [ ] evidence is saved for every advanced verdict
- [ ] partial fixes can be demonstrated
- [ ] regressions can be demonstrated
- [ ] a benchmark of roughly 10 or more cases exists
- [ ] primary metric is computed automatically
- [ ] baseline vs advanced results are generated automatically
- [ ] at least one difficult case is documented
- [ ] at least one attempted experiment is removed based on evidence
- [ ] clean-environment setup is verified
- [ ] all agent trajectories required for submission are captured
- [ ] final README includes user, bottleneck, value, changelog, failure mode, and hot take

---

## 20. MVP Philosophy

Do less, but prove more.

The MVP does not need to verify arbitrary software patches.

It needs to show, convincingly and reproducibly, that **forcing an agent to reproduce, execute, challenge, and verify a patch produces better judgments than asking an agent whether the patch looks correct.**
