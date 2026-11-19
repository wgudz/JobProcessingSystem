
# AG-110 — Analysis plan

The agent creates an analysis plan before the first tool call.

Each step contains:

- tool and arguments,
- purpose,
- decisive result,
- fallback,
- execution status.

The plan is not evidence. Only tool results stored as `EVID-*`
are evidence.

## Limits

The session keeps the existing `MAX_TOOL_CALLS = 24` budget.

A plan is complete when all required steps reached a terminal state
(`DONE`, `FAILED` or `SKIPPED`) and at least one required step
produced evidence.

After the plan is complete, no additional tools are exposed to
the model.

## Skipped execution

Tests requiring execution may be marked `SKIPPED`.

A skipped test does not confirm the conclusion and is reported as
a limitation.

## Replanning

The original plan is stored as revision 1.

Later revisions are appended and never replace older revisions.

When a selected test fails, code inspection may be moved before
remaining tests.

The report contains:

- current analysis plan,
- plan history,
- executed evidence flow.

This allows comparison of planned and actual execution.
