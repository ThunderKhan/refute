# PRD.md

# refute — Product Requirements Document

## 1. Product Summary

`refute` is an agentic patch-verification tool for determining whether a proposed software patch genuinely fixes a reported bug.

Instead of relying on static code inspection alone, `refute` attempts to reproduce the defect, executes the patch against the same failure, challenges the patch with nearby cases, checks for regressions, and returns an evidence-backed verdict.

The product is intentionally designed around **falsification rather than trust**.

---

## 2. Product Goal

Enable a maintainer to answer:

> **“Did this patch actually fix the reported bug?”**

with executable evidence rather than a plausibility judgment.

---

## 3. Intended User

### Primary Persona: Maintainer Reviewing a Patch

A maintainer receives a bug report and a candidate fix.

They may not know the relevant subsystem deeply and may have limited time.

They need to determine whether the patch:

- fixes the reported behavior,
- fixes the underlying failure rather than one narrow example,
- avoids obvious regressions,
- and deserves further human approval.

### User Constraints

The user:

- cannot spend unlimited time manually constructing reproductions,
- may not trust existing tests to capture the bug,
- may be reviewing unfamiliar code,
- and needs a verdict that can be audited.

---

## 4. User Problem

Existing patch review workflows often rely on:

- reading the diff,
- running the repository's current tests,
- and manually reasoning about correctness.

This can fail because existing tests may never reproduce the reported issue.

LLM-based reviews amplify this risk when they provide confident textual conclusions without runtime evidence.

---

## 5. Product Promise

> **Give `refute` a bug report, repository, and candidate patch. It will try to prove the patch wrong and show the evidence behind its verdict.**

---

## 6. Non-Goals

The MVP will not:

- support every programming language,
- automatically merge or publish patches,
- modify remote repositories,
- act as a replacement for human maintainers,
- prove formal correctness,
- guarantee absence of all regressions,
- execute untrusted code outside a controlled environment,
- or evaluate security-critical patches as an authoritative security review.

---

## 7. Core Inputs

A verification run requires:

### Required
- repository path or bundled benchmark case
- bug/issue description
- candidate patch or patched version

### Optional
- existing test command
- reproduction hint
- affected file hints
- expected output
- constraints supplied by the maintainer

---

## 8. Core Outputs

Each run should produce:

### Human-readable result
- final verdict
- confidence or evidence sufficiency
- issue interpretation
- reproduction summary
- before/after result
- adversarial cases attempted
- regressions found
- limitations

### Machine-readable result
A structured JSON report containing fields such as:

```json
{
  "case_id": "case_004",
  "verdict": "partial_fix",
  "original_bug_reproduced": true,
  "patched_case_passed": true,
  "regression_detected": false,
  "adversarial_failures": 1,
  "evidence": [],
  "limitations": []
}
```

### Evidence artifacts
- command log
- test output
- generated reproduction test
- generated adversarial tests
- baseline output
- advanced output

---

## 9. User Workflow

### Command-level flow

```text
refute verify <case-or-repo>
        ↓
load issue + patch + repository
        ↓
understand reported behavior
        ↓
inspect relevant code and tests
        ↓
construct reproduction
        ↓
run against original
        ↓
run against patched
        ↓
challenge with nearby cases
        ↓
run regression checks
        ↓
assemble evidence
        ↓
return verdict
```

---

## 10. Functional Requirements

### FR-1: Case Loading
The system must load a verification case containing:

- issue text,
- original code,
- patched code or patch diff,
- test configuration,
- and case metadata.

### FR-2: Issue Interpretation
The system must derive:

- reported behavior,
- expected behavior,
- likely trigger conditions,
- and uncertainty or missing information.

### FR-3: Repository Inspection
The system must identify:

- relevant files,
- likely execution path,
- existing tests,
- and project test command.

### FR-4: Reproduction Generation
The system must attempt to create an executable reproduction of the reported failure.

The generated reproduction should be saved as an artifact.

### FR-5: Original Failure Verification
The system must execute the reproduction against the original buggy version.

If the failure cannot be reproduced, this must be explicitly recorded.

### FR-6: Patched Behavior Verification
The same reproduction must be executed against the patched version.

### FR-7: Adversarial Case Generation
The system should generate nearby cases derived from:

- boundaries,
- neighboring input classes,
- variants of the trigger condition,
- or assumptions discovered during analysis.

### FR-8: Regression Check
The system must run relevant existing tests or benchmark-specific checks against the patched version.

### FR-9: Evidence Collection
All material claims must be linked to evidence such as:

- command output,
- test result,
- file path,
- generated test,
- or observed runtime behavior.

### FR-10: Verdict Generation
The system must classify the patch as:

- `complete_fix`
- `partial_fix`
- `ineffective_fix`
- `regression_introduced`
- `inconclusive`

### FR-11: No Fabricated Evidence
If a required observation cannot be established, the system must say so.

### FR-12: Baseline Runner
The repository must contain a baseline implementation that reviews the same case without runtime verification.

### FR-13: Evaluation Runner
The project must support an evaluation command that runs baseline and advanced methods against the same benchmark cases and generates aggregate metrics.

---

## 11. Agentic Architecture

The exact implementation may evolve during experimentation, but the initial architecture should separate four roles conceptually.

### Investigator
Responsibilities:
- understand the issue,
- inspect repository context,
- identify relevant files,
- propose reproduction strategy.

### Executor
Responsibilities:
- run commands,
- execute tests,
- capture stdout/stderr,
- compare original and patched behavior.

### Challenger
Responsibilities:
- search for boundary conditions,
- generate nearby failure cases,
- attempt to falsify a tentative “complete fix” conclusion.

### Verifier
Responsibilities:
- evaluate the collected evidence,
- reject unsupported claims,
- produce the final verdict.

These may be implemented as separate agents, separate prompts, or stages of one orchestrated agent. The architecture should remain evidence-driven: components are retained only if evaluation shows that they help.

---

## 12. Baseline Design

The baseline must use the same core case inputs.

### Baseline procedure
1. Read issue description.
2. Read patch diff.
3. Read limited relevant repository context.
4. Ask one general-purpose coding agent whether the patch fixes the issue.
5. Record its verdict and explanation.

### Baseline restrictions
The baseline does not:
- run tests,
- construct a reproduction,
- generate adversarial cases,
- or verify conclusions through execution.

This creates a clear comparison between **static plausibility judgment** and **agentic executable verification**.

---

## 13. Benchmark Design

### Minimum target
10 cases.

### Preferred target
12–20 cases if implementation time permits.

### Case classes
The benchmark should include:

1. complete fix
2. partial fix
3. ineffective patch
4. exact-input overfit
5. boundary-condition miss
6. regression-introducing fix
7. unrelated patch
8. fix where existing tests already catch the bug
9. fix where existing tests do not catch the bug
10. challenging ambiguous case

### Ground truth
Each case must have a known expected verdict backed by deterministic tests or a fixture-specific oracle.

---

## 14. Evaluation

### Primary Metric
**Patch Verdict Accuracy**

### Secondary Metrics
- false acceptance rate
- reproduction success rate
- regression detection rate
- adversarial failure discovery rate
- runtime
- approximate model cost
- number of retries/tool calls where useful

### Fairness Requirement
Baseline and advanced workflow must be evaluated on the **same cases**.

Any meaningful resource difference must be documented.

---

## 15. Reproducibility Requirements

A clean-environment user must be able to run:

```bash
# baseline
<command>

# advanced solution
<command>

# evaluation
<command>
```

The final repository must document:

- supported Python version
- dependency versions
- exact setup commands
- benchmark data
- expected output
- approximate runtime
- approximate cost
- model/provider assumptions

---

## 16. Safety and Execution Model

`refute` executes repository code, so execution must be constrained.

For the hackathon MVP:

- use only bundled/synthetic/approved benchmark repositories,
- execute locally in an isolated temporary workspace,
- enforce timeouts,
- avoid network access during benchmark execution where practical,
- never expose credentials,
- never merge or publish patches automatically,
- and require human approval for any real repository action outside the benchmark.

---

## 17. UX Requirements

The CLI should make the verdict obvious.

Example:

```text
refute — case_004

VERDICT: partial_fix

Original failure:
  reproduced

Reported case after patch:
  passes

Existing regression suite:
  passes

Adversarial checks:
  1 failure found

Evidence:
  artifacts/case_004/repro_test.py
  artifacts/case_004/adversarial_02.py
  artifacts/case_004/test_output.txt

Reason:
  The patch handles the reported value but fails for the adjacent
  boundary condition, indicating the underlying defect remains.

Limitations:
  Only the affected parser path and repository test suite were evaluated.
```

The final result should feel like an engineering artifact, not a generic AI response.

---

## 18. Improvement Changelog Strategy

Every meaningful experiment must record:

| Stage | What changed | Why | Evidence | Decision |
|---|---|---|---|---|
| Baseline | Static review only | Establish starting point | Eval result | Keep as baseline |
| Iteration 1 | Add execution | Test whether runtime evidence improves accuracy | Eval result | TBD |
| Iteration 2 | Add reproduction synthesis | Existing tests may miss reported defects | Eval result | TBD |
| Iteration 3 | Add challenger/adversarial cases | Detect partial fixes | Eval result | TBD |
| Removed experiment | TBD | TBD | Eval result | Remove if not useful |
| Final | Best-performing combination | Evidence-driven | Final eval | Ship |

Do not pre-fill results. Results must come from actual runs.

---

## 19. Acceptance Criteria

The MVP is acceptable when:

- [ ] baseline is runnable
- [ ] advanced workflow is runnable
- [ ] evaluation uses the same cases for both
- [ ] at least 10 benchmark cases exist, if time permits
- [ ] every case has ground truth
- [ ] original and patched code can be executed
- [ ] verdict output is structured
- [ ] evidence artifacts are persisted
- [ ] at least one adversarial case path exists
- [ ] exact reproduction commands are documented
- [ ] at least one challenging case is discussed
- [ ] at least one experiment is explicitly rejected or removed based on evidence
- [ ] final README includes intended user, bottleneck, value, main failure mode, and final hot take
- [ ] agent trajectories are captured for every agent used

---

## 20. Final Product Principle

`refute` should optimize for **defensible uncertainty**, not confident completion.

If it cannot prove enough, it should say:

> `inconclusive`

A trustworthy verifier must be able to admit when the available evidence is insufficient.
