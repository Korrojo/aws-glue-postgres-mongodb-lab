## Roadmap task

- Task ID:
- Roadmap status before PR:
- Roadmap status proposed by PR:
- Design sections implemented:

## Scope

- Objective:
- Files/directories intentionally changed:
- Files/directories intentionally not changed:

## Security

- [ ] No secrets, credentials, keys, live endpoints, Terraform state, or plans are included.
- [ ] Public-repository safety was considered.
- [ ] IAM and network changes are least-privilege and lab-scoped.
- [ ] Logs and evidence are redacted.

## Infrastructure and cost

- Terraform plan summary:
- New or changed billable resources:
- Expected lab-session cost impact:
- Destroy/rollback behavior:
- [ ] No NAT Gateway was introduced.
- [ ] Required project tags are present.

## Tests

Credential-free commands run and observed results (static/mock/Terraform validation/Python unit/local container only):

```text
<command and result>
```

- [ ] No AWS credentials were requested, obtained, or used.
- [ ] No AWS call, live Terraform operation, Glue execution, resource creation, or teardown validation was performed by an agent.
- [ ] No agent-run live AWS evidence is required.

User-run-only AWS commands: not an agent PR gate. Record only user-supplied redacted results, or state `not run — user-run only after clone`.

```text
<user-supplied command/result or not run — user-run only after clone>
```

Skipped credential-free checks and reason:

## Acceptance criteria

- Criteria satisfied:
- Criteria remaining:

## Documentation

- [ ] README/runbook updated where behavior changed.
- [ ] The implementing worker updated the affected runbook in this PR.
- [ ] Commands include prerequisites, run location, expected result, verification, reset/rerun behavior, and focused troubleshooting.
- [ ] AWS commands are labeled **User-run only**; their expected results are documented but not claimed as agent-observed.
- [ ] No unnecessary production-grade component was introduced.
- [ ] ROADMAP status and PR reference updated.
- [ ] Limitations and future work are explicit.

## Agent handoff

- Worker(s):
- Timeout/recovery event, if any:
- Remaining blocker or exact next action:

## Merge control

- [ ] This PR is ready for Demes's review.
- [ ] Auto-merge is disabled.
- [ ] Hermes/Codex has not merged this PR.
