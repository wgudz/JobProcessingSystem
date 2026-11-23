---
name: job-regression-triage
description: Diagnose one regression in JobProcessingSystem C++20 using Git state, a minimal reproducing CTest, source and test evidence, and a minimal proposed fix.
---
# Job Regression Triage

Use this Skill only for diagnosis of a single regression in
JobProcessingSystem.

The goal is to reproduce the reported symptom, connect it to
specific code evidence and propose the smallest justified change.

Do not apply source changes.

## Investigation order

Follow this order unless collected evidence clearly justifies
changing it:

1. Check repository state with `git_status`.
2. Reproduce the reported symptom with the smallest relevant test.
3. Read the test that defines the expected behaviour.
4. Inspect the relevant implementation.
5. Inspect repository changes with `git_diff` or `git_show` when
   they are relevant to the regression.
6. Compare observed behaviour with the behaviour required by the test.
7. Propose the smallest justified fix.
8. Define verification that must be performed after the fix.

Do not run unrelated tests only to collect more evidence.

Do not stop the investigation only because the focused test passes.

Before producing the final response, collect evidence for:

- repository state,
- focused reproduction,
- the relevant test source,
- the relevant implementation or code change,
- comparison between observed and expected behaviour.

If the focused test passes, report that the symptom was not reproduced,
but still inspect the test and relevant code before finishing.

Use actual tool calls to collect evidence. Do not merely describe a tool
that should be called.

The Skill instructions are already present in the model context.

Do not use `read_file` to inspect `skills/`, `issues/` or `reports/`.

Use `read_file` only with repository-relative paths under `tests/`,
`src/`, `include/` or `app/`.

Use `search_code` to locate relevant implementation files before reading
an implementation path that is not already known.

Do not propose a source fix when the reported regression was not reproduced
and no evidence identifies a defect.

## Minimal reproducing test

Prefer one test that directly covers the reported module.

Selection priority:

1. a valid test explicitly named in the incident,
2. a test selected from the project test mapping,
3. a broader test only when no focused test can reproduce the issue.

A selected test is diagnostic evidence.

A full CTest run is not the first reproduction step.

After a C++ fix is actually applied, full CTest is required before
the fix can be described as verified.

If execution is not allowed, do not bypass the restriction.
Continue with read-only evidence and clearly state that reproduction
was not confirmed.

## Facts and hypotheses

A fact about source code or tests must reference an existing
`EVID-*` identifier.

Finding a suspicious condition, branch or `if` is not enough to
confirm a root cause.

Treat a possible mechanism as a hypothesis until evidence connects:

- the reported symptom,
- the reproducing test,
- the expected behaviour,
- and the relevant implementation or change.

Do not turn a hypothesis into a fact only because it looks plausible.

## Required response content

The final response must use these headings exactly and contain no
introductory text before them:

## Facts

## Hypotheses

## Minimal fix

## Test plan

## Risks

## Final result

Keep the standard report headings required by the runner.

Under them provide the following information.

### `## Facts`

Include:

- `Symptom:` what was reported or reproduced,
- `Reproduction:` which focused test reproduced the problem, or that
  reproduction was not confirmed,
- `Evidence:` relevant `EVID-*` references and paths.

### `## Hypotheses`

Include:

- `Mechanism:` the suspected technical mechanism.

Clearly say whether the mechanism is confirmed or still a hypothesis.

### `## Minimal fix`

Include:

- `Proposed fix:` the smallest change justified by the evidence.

Do not propose unrelated refactoring.

### `## Test plan`

Include:

- `Tests:` the focused reproducing test and the verification required
  after an applied fix.

Full CTest is mandatory before claiming that an applied C++ fix is
verified.

### `## Risks`

Include:

- `Risks:` possible side effects of the proposed change,
- `Uncertainties:` missing evidence, skipped execution or unresolved
  assumptions.

### `## Final result`

State whether the regression was:

- reproduced and technically explained,
- reproduced but the mechanism remains uncertain,
- or not reproduced / not confirmed.

Do not claim verification from the plan alone.

## Example incident

```json
{
  "title": "Queue test started failing after a recent change",
  "symptoms": "thread_safe_queue_test fails during queue shutdown behaviour",
  "expected": "The queue should preserve its documented shutdown behaviour",
  "suspected_tests": [
    "thread_safe_queue_test"
  ]
}
```
