
# AG-109 — Markdown and JSON reports

## Markdown order

1. Issue
2. Environment
3. Verification scope
4. Facts
5. Hypotheses
6. Proposed minimal change
7. Test plan
8. Risks
9. Final result

Facts without an `EVID-*` reference are marked
`[UNVERIFIABLE]`.

## Machine report

Required top-level fields:

- `session_id`
- `issue_id`
- `status`
- `model`
- `repo_head`
- `events`
- `findings`
- `verification`
- `limitations`

`events` contain real tool results.

`findings` contain model-generated conclusions.

Model text is never used as a command exit code.

The current read-only agent does not emit
`verified_fix`, because it does not apply suggested
source changes and therefore cannot execute a build
and CTest after applying its own fix.

The report format is checked by
`validate_machine_report()` and both outputs are
cross-checked by `validate_report_consistency()`.
