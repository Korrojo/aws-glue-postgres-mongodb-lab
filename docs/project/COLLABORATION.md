# Hermes and Codex Collaboration Model

## Authority

- Demes approves design changes and merges.
- `DESIGN.md` defines architecture and scope.
- `ROADMAP.md` defines task order, status, branch, and PR grouping.
- `AGENTS.md` defines implementation and safety rules.
- Hermes coordinates tasks and reports results.
- Codex workers implement only the bounded assignment they receive.

## Required workflow

1. Hermes selects the next unblocked task from `ROADMAP.md`.
2. Hermes changes its status to `IN PROGRESS` on the task branch.
3. Hermes gives a Codex worker a bounded assignment containing:
   - task ID;
   - exact objective;
   - allowed files/directories;
   - files that must not be touched;
   - acceptance criteria;
   - required commands;
   - dependency and design references.
4. The worker reads the repository instructions before editing.
5. The worker implements and tests on the assigned branch.
6. The worker completes the affected runbook instructions using observed commands and results in the same branch.
7. Hermes reviews the diff, checks scope and documentation completeness, runs or verifies required tests, and updates the roadmap.
8. Hermes opens a PR using the template and stops for Demes's review.
9. Demes decides whether to merge.

## Worker assignment template

```text
Task: <TASK-ID> — <title>
Branch: <branch>
Objective: <one bounded outcome>

Read first:
- AGENTS.md
- docs/project/DESIGN.md
- docs/project/ROADMAP.md
- docs/project/ACCEPTANCE_CRITERIA.md
- docs/project/DOCUMENTATION_STANDARD.md

Allowed files:
- <paths>

Do not modify:
- <paths>

Required implementation:
- <items>

Required checks:
- <commands>

Required documentation:
- <affected docs/runbook file>
- include prerequisites, exact commands, expected results, verification, reset, and troubleshooting

Stop conditions:
- design conflict;
- missing permission;
- secret exposure risk;
- destructive target cannot be resolved exactly;
- task requires files owned by another active task.

Return:
- changed files;
- test results;
- remaining limitations;
- exact next action if incomplete.
```

## Timeout and recovery rules

If a worker times out or stops mid-task:

1. Do not merge partial work.
2. Do not create a new branch for the same task.
3. Inspect the existing branch and working tree.
4. Record:
   - latest commit;
   - changed/uncommitted files;
   - completed checklist items;
   - failing command and relevant error;
   - next exact step.
5. Resume with a worker on the same task and branch using that handoff.
6. If the task was too broad, split remaining work only within the same roadmap PR grouping and document the split.

Documentation is part of the same task. Do not hand incomplete runbooks to an unrelated final documentation worker.

## Parallel-work rule

Parallel work is allowed only when:

- dependencies are complete;
- allowed file sets do not overlap;
- Terraform state/configuration ownership does not overlap;
- both branches can be reviewed independently;
- Hermes records the ownership boundaries before delegation.

Default behavior is sequential implementation.

## Merge rules

Hermes and workers must not:

- merge PRs;
- enable auto-merge;
- push directly to `main`;
- rewrite public repository history;
- bypass required checks;
- combine unrelated cleanup into a task;
- mark a task `DONE` before the merged PR is recorded.

## Design-change process

When implementation reveals a design issue:

1. Mark the task `BLOCKED`.
2. Describe the observed evidence.
3. Identify the exact design section affected.
4. Present the smallest supported options and tradeoffs.
5. Wait for Demes's decision.
6. Update `DESIGN.md` and the roadmap through a dedicated reviewed change before implementation continues.
