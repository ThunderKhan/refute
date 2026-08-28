# PROBLEM_STATEMENT.md

# refute — Problem Statement

## 1. Problem

Software maintainers regularly review patches that appear correct, compile successfully, and may even pass the repository's existing test suite, yet still fail to resolve the actual reported bug.

A patch can fail in several ways:

- It may only handle the exact input described in the issue.
- It may fix one symptom while leaving the underlying defect intact.
- It may make the current tests pass without reproducing the reported behavior.
- It may introduce a nearby regression.
- It may modify unrelated behavior while appearing plausible in static review.
- It may be accepted because a reviewer or coding agent says it “looks correct,” without executable evidence.

The practical bottleneck is not simply reading the patch. It is **establishing whether the patch genuinely fixes the bug**.

Today, that verification often requires a maintainer to manually combine:

- the original issue report,
- repository structure,
- relevant implementation code,
- existing tests,
- expected behavior,
- reproduction steps,
- the proposed patch,
- and possible edge cases.

This process is slow, inconsistent, and easy to shortcut.

---

## 2. Target User

The primary intended user is:

> A software maintainer or engineer reviewing a bug-fix patch in an unfamiliar or moderately complex codebase.

Secondary users may include:

- open-source maintainers,
- code reviewers,
- QA engineers,
- contributors validating their own fixes,
- engineering teams triaging incoming patches,
- and developers using coding agents to implement bug fixes.

---

## 3. Core User Pain

The user needs to answer a deceptively simple question:

> **Did this patch actually fix the bug?**

A normal code review or LLM review can provide a plausible opinion, but the user needs stronger evidence.

The painful part is that correctness is often hidden behind execution:

1. Was the reported bug reproducible before the patch?
2. Does the same reproduction succeed after the patch?
3. Does the patch only fix the reported example, or the broader failure class?
4. Did the patch introduce a regression elsewhere?
5. Can the verdict be traced back to actual commands, test results, and observed behavior?

---

## 4. Challenge Statement

Build an **agentic patch-verification system** that independently determines whether a proposed code change genuinely resolves a reported software defect.

The system should not merely review source code and produce an opinion.

It should attempt to **falsify the claim that the patch is correct** by gathering executable evidence.

The workflow should:

1. interpret the issue or bug report,
2. identify expected and actual behavior,
3. inspect the relevant repository context,
4. construct or recover a reproduction,
5. execute the reproduction against the unpatched version,
6. confirm the original failure,
7. execute the same reproduction against the patched version,
8. generate nearby or adversarial cases where appropriate,
9. check for regressions,
10. and produce an evidence-backed verdict.

---

## 5. Expected Verdicts

The system should classify a proposed patch into one of the following:

### `complete_fix`
The original defect is reproduced before the patch, no longer reproduced after the patch, and no relevant regression is discovered within the evaluated scope.

### `partial_fix`
The reported case is improved or resolved, but a closely related case still fails or the broader defect remains.

### `ineffective_fix`
The patch does not resolve the original defect.

### `regression_introduced`
The original issue may be fixed, but the patch causes a new failure in relevant behavior.

### `inconclusive`
The system cannot establish enough evidence to make a defensible judgment.

`inconclusive` is an important outcome. The system should prefer uncertainty over fabrication.

---

## 6. Baseline

The baseline represents a reasonable basic way to handle the task before the advanced workflow.

### Baseline approach

A single general-purpose coding agent receives:

- the issue text,
- the patch diff,
- and relevant repository context.

It is asked:

> “Does this patch fix the reported bug? Explain your reasoning.”

The baseline performs **static reasoning only**.

It does not:

- independently reproduce the issue,
- execute the original and patched code,
- generate adversarial cases,
- or verify its own conclusion through runtime evidence.

---

## 7. Advanced Solution

The advanced system, `refute`, adds explicit verification.

Its core principle is:

> **A claim about correctness should survive attempts to falsify it.**

The advanced workflow may include specialized stages for:

- issue interpretation,
- repository inspection,
- reproduction synthesis,
- execution,
- adversarial case generation,
- regression testing,
- and evidence-backed verdict generation.

The advanced solution must only retain components that demonstrably improve the result.

---

## 8. Primary Evaluation Question

> **Can `refute` classify bug-fix patches more accurately than a simple static-review baseline when both are evaluated on the same bug/patch cases?**

---

## 9. Primary Metric

### Patch Verdict Accuracy

For each evaluation case, compare the predicted verdict with the known ground-truth verdict.

\[
\text{Verdict Accuracy} =
\frac{\text{Correct Verdicts}}{\text{Total Cases}}
\]

This is the primary metric because it directly reflects the user's goal: correctly determining whether a patch fixes a bug.

---

## 10. Secondary Metrics

Where practical, also report:

- **False Acceptance Rate**  
  How often an incorrect or partial patch is incorrectly accepted as a complete fix.

- **Reproduction Success Rate**  
  How often the system successfully reproduces the original defect.

- **Regression Detection Rate**  
  How often introduced regressions are correctly detected.

- **Adversarial Case Yield**  
  How often generated nearby cases reveal a failure not captured by the original report.

- **Runtime per case**

- **Approximate model/API cost per case**

- **Human intervention required**

---

## 11. Evaluation Dataset

The MVP should use a controlled benchmark of at least 10 bug/patch cases when time allows.

Each case should include:

- issue description,
- repository or fixture,
- original buggy version,
- candidate patch,
- expected verdict,
- deterministic tests or oracle,
- and one or more known relevant edge cases where appropriate.

The dataset should include a mixture of:

- complete fixes,
- partial fixes,
- ineffective fixes,
- patches that overfit to the reported example,
- and patches that introduce regressions.

At least one challenging case should be included and discussed explicitly.

---

## 12. Scope Constraints

To keep the project achievable and reproducible during the hackathon, the initial version should be deliberately narrow.

Recommended MVP scope:

- Python repositories only
- `pytest`-based evaluation
- local repositories or bundled benchmark fixtures
- no automatic interaction with live production systems
- no automatic merging or committing of patches
- all execution in a controlled local sandbox/workspace
- human remains responsible for any real-world code integration decision

The project should optimize for **depth and evidence**, not universal language support.

---

## 13. Success Criteria

The project is successful if:

1. the baseline and advanced system can run on the same fixed cases,
2. `refute` produces a measurable improvement in verdict accuracy or false-acceptance rate,
3. every final verdict is linked to observable evidence,
4. the workflow can be reproduced from a clean environment,
5. at least one meaningful iteration is supported by evaluation evidence,
6. at least one experiment is removed or rejected based on evidence,
7. and the final output is useful enough that a maintainer could use it during patch review.

---

## 14. Product Principle

`refute` is not intended to replace maintainers.

It is intended to make a maintainer's judgment better grounded.

The system should not say:

> “This patch looks correct.”

It should say something closer to:

> “The original failure was reproduced before the patch, the same case passes after the patch, but a neighboring boundary case still fails. Verdict: partial fix.”

---

## 15. Working Hot Take

> **Coding agents become more trustworthy when they are forced to produce evidence that can prove them wrong.**

This is a working hypothesis, not a predetermined conclusion. The final hot take should be rewritten from the actual evaluation results.
