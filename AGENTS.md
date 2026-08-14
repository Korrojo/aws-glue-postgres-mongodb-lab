# Repository Agent Rules

These rules apply to Hermes, Codex, and every delegated worker in this repository.

## Required reading

Before editing, read:

1. `docs/project/DESIGN.md`
2. `docs/project/ROADMAP.md`
3. `docs/project/COLLABORATION.md`
4. `docs/project/ACCEPTANCE_CRITERIA.md`
5. `docs/project/DOCUMENTATION_STANDARD.md`

The design is authoritative. Do not reinterpret or expand it silently.

## Scope and task control

- Work only on an assigned roadmap task ID.
- Use the branch recorded for that task.
- Do not edit files assigned to another active task.
- Do not introduce Oracle, CDC, DMS, Kafka, Kinesis, Atlas, DocumentDB, Kubernetes, CI deployment credentials, a NAT Gateway, or a multi-node MongoDB deployment in version 1.
- Do not replace Terraform, Docker Compose, AWS Glue, PostgreSQL, or MongoDB with alternatives.
- Do not add production-hardening work that is outside the design.
- Prefer the shortest implementation that covers the learning objective, is repeatable, protects credentials, and can be destroyed safely.
- Do not add multi-environment configuration, remote Terraform state, release automation, deployment pipelines, base-image pipelines, autoscaling, high availability, custom dashboards, policy-as-code frameworks, or reusable enterprise module hierarchies.
- Record a design question as a blocker; do not resolve it through an undocumented architectural change.

## Git and pull requests

- Never push directly to `main`.
- Never merge or enable auto-merge.
- Use branches named `agent/hermes-codex/<task-id>-<short-name>`.
- One roadmap task may span only the PR grouping defined in `ROADMAP.md`.
- Update the roadmap status and PR field in the same PR that completes the task.
- Complete the pull-request template fully.
- Keep commits intentional and reviewable.
- If a worker times out, resume the same task and branch; do not create a competing branch or duplicate PR.

## Public-repository safety

This repository is permanently public.

Never commit:

- AWS account IDs when a placeholder or runtime lookup is sufficient;
- database passwords or connection strings containing credentials;
- `.env` files;
- private or deploy keys;
- Terraform state, plans, crash logs, or `.terraform/` contents;
- AWS CLI caches or credentials;
- Glue connection exports containing credentials;
- generated reconciliation data containing secrets;
- public IP addresses from a live lab run;
- client, employer, or work-system data.

All examples must use synthetic data. Logs and test fixtures must be safe for a public repository.

## Infrastructure safety

- All AWS resources must be Terraform-managed unless the design explicitly marks a step as manual.
- Every resource that supports tags must include `Project=aws-glue-postgres-mongodb-lab`, `Environment=lab`, and `ManagedBy=terraform`.
- Terraform must use an isolated local state file that is gitignored for version 1.
- Destructive scripts must resolve and verify the exact project and Terraform working directory before acting.
- Never delete by broad name pattern, unverified environment variable, account scope, VPC scope, or wildcard.
- Do not use a NAT Gateway.
- Do not open ports 22, 5432, or 27017 to the public internet.
- EC2 administration is through AWS Systems Manager Session Manager and Run Command.
- Database credentials must be stored in AWS Secrets Manager and must not be created as Terraform secret values.

## Implementation standards

- Keep the Glue entry script thin; put reusable transformations and validation logic under `src/glue_lab/`.
- Use deterministic MongoDB `_id` values derived from PostgreSQL `order_id`.
- Preserve decimal precision through transformation and validate exact totals.
- Fail the job on invalid primary keys, orphan items, invalid quantity, or invalid price.
- Use standard PySpark transformations; do not collect the complete dataset to the driver.
- Separate unit tests from AWS integration tests.
- Mock only service boundaries; do not mock transformation behavior that can be tested with a small Spark DataFrame.
- Pin dependencies and commit the dependency lock files appropriate to the chosen tooling.
- Scripts must use strict shell mode and redact sensitive values.

## Documentation standards

- The README is the front door and sequence overview. It is not the complete lab manual.
- The worker implementing a component must update the corresponding `docs/runbook/` file in the same PR.
- Follow `docs/project/DOCUMENTATION_STANDARD.md` exactly.
- Every runnable step must contain:
  - purpose;
  - where the command runs;
  - prerequisites and required inputs;
  - exact copy/paste command;
  - expected result;
  - verification command and pass condition;
  - repeat/reset or rollback behavior;
  - narrowly relevant troubleshooting.
- Never write “configure,” “set up,” “deploy,” “verify,” or “run the job” without the actual commands and expected result.
- Never hide required steps behind assumed AWS, Terraform, Docker, Git, PostgreSQL, MongoDB, or Glue knowledge.
- Use placeholders only when the user must supply a value; define every placeholder immediately before use.
- Keep troubleshooting diagnostic. Do not solve a lab failure by adding production infrastructure.

## Required checks before PR handoff

Run all checks relevant to changed files:

```bash
make format-check
make lint
make unit-test
make compose-check
make terraform-check
```

For AWS integration PRs, also provide the applicable evidence from:

```bash
make doctor
make deploy
make crawl
make run
make validate
make rerun-test
make cost-check
make destroy-lab
```

Do not claim a command passed unless its output was observed in the current branch.
