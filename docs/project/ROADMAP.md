# Roadmap and To-Do

## Status values

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `PR OPEN`
- `DONE`

`DONE` means the reviewed implementation and credential-free development checks are complete. Live AWS execution is not a task status or agent acceptance gate; it is user-run only.

Only one task may be `IN PROGRESS` unless Hermes proves that file ownership and dependencies do not overlap. `GLUE-050` and `GLUE-060` were delivered together in [PR #6](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/6) and are now `DONE`. `GLUE-070` was delivered in [PR #8](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/8) and is now `DONE`. `GLUE-080` is a documentation-only correction that standardizes the AWS CLI profile name across the ordered runbooks.

## Credential-free development acceptance

Agents must never request or use AWS credentials or execute any AWS command. Static checks, mocks, Terraform validation/mock-provider tests, Python/Spark unit tests, and local container tests are sufficient for development completion. AWS deployment, crawler/job execution, connection tests, and teardown are **user-run only** after cloning the completed repository. No agent-run live AWS evidence is required. A later user-run failure must become a separate issue/PR.

## Summary

| Task | Status | PR | Depends on | Outcome |
|---|---|---|---|---|
| `GLUE-000` | DONE | [#1](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/1) | — | Governance and repository skeleton |
| `GLUE-010` | DONE | [#2](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/2) | `GLUE-000` | Containerized source/target and fixtures |
| `GLUE-020` | DONE | [#3](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/3) | `GLUE-010` | Disposable AWS foundation and EC2 workflow |
| `GLUE-025` | DONE | [#4](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/4) | `GLUE-020` | Foundation teardown and persistent-volume rotation correction |
| `GLUE-030` | DONE | [#5](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/5) | `GLUE-025` | Glue networking, connections, crawler, catalog |
| `GLUE-040` | DONE | [#5](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/5) | `GLUE-030` | PySpark transformation and MongoDB load |
| `GLUE-050` | DONE | [#6](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/6) | `GLUE-040` | Reconciliation and rerun validation |
| `GLUE-060` | DONE | [#6](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/6) | `GLUE-050` | Runbook, cleanup proof, final release |
| `GLUE-070` | DONE | [#8](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/8) | `GLUE-060` | First-time prerequisite onboarding and explanations |
| `GLUE-080` | PR OPEN | [#10](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/10) | `GLUE-070` | Consistent AWS CLI profile naming across runbooks |

## `GLUE-000` — Governance and repository skeleton

Branch: `agent/hermes-codex/glue-000-governance`  
PR grouping: PR 1 only

### To-do

- [x] Create the public repository with MIT license.
- [x] Install `AGENTS.md` and all `docs/project/` documents.
- [x] Install the PR template.
- [x] Add a short root README containing objective, architecture summary, total lab sequence, cost warning, current project status, and links to the detailed runbooks. The README must not duplicate or replace the runbooks.
- [x] Install `DOCUMENTATION_STANDARD.md` and every `docs/runbook/` template from the handoff package.
- [x] Add `.gitignore` entries for Terraform state/plans, `.terraform/`, `.env*` except `.env.example`, keys, Python caches, test output, IDE files, generated artifacts, and secrets.
- [x] Add `.env.example` containing names/placeholders only.
- [x] Create the repository directory skeleton from `DESIGN.md`.
- [x] Add Makefile targets as documented stubs with help text; unimplemented targets must fail clearly rather than succeed silently.
- [x] Add minimal CI scaffolding for secret scanning, Python unit tests, Docker Compose validation, and Terraform formatting/validation. Do not add deployment workflows or an enterprise CI framework.
- [x] Add dependency files with pinned or constrained versions appropriate to Glue 5.1.
- [x] Confirm no credential, account-specific value, or generated state is tracked.
- [x] Update this task to `PR OPEN` and record the PR number.

### Acceptance

- Governance-only PR.
- CI scaffolding is syntactically valid.
- Documentation templates and standards are installed.
- No AWS call, Docker start, or deployed resource.
- All later roadmap tasks remain `NOT STARTED`.
- No auto-merge.

## `GLUE-010` — Docker data layer and deterministic fixtures

Branch: `agent/hermes-codex/glue-010-data-layer`  
PR grouping: PR 2 only

### To-do

- [x] Add pinned PostgreSQL and MongoDB Community container images compatible with the lab architecture and Mac/EC2 platforms.
- [x] Add health checks and named volumes.
- [x] Bind database ports in a way compatible with EC2 private-IP access while relying on security groups for AWS isolation.
- [x] Create `sales.orders` and `sales.order_items` with constraints.
- [x] Add deterministic valid seed data.
- [x] Add isolated invalid fixtures for failure-path tests.
- [x] Initialize the MongoDB `migration_lab` database and least-privilege Glue writer user.
- [x] Add local container smoke tests.
- [x] Add source SQL assertions for counts, keys, foreign keys, decimals, and soft deletes.
- [x] Document Apple Silicon compatibility without introducing an alternate architecture.
- [x] Complete `docs/runbook/02-START-DATABASES.md` in the same PR, including prerequisites, exact commands, expected output, verification, reset, and focused troubleshooting.
- [x] Implement `make local-up`, `make local-status`, `make local-test`, and `make local-down`.
- [x] Ensure no secret values are embedded in Compose or initialization files.

### Acceptance

- Containers become healthy from a clean checkout with locally supplied secrets.
- Seed rerun is deterministic.
- Valid source assertions pass.
- Invalid fixtures fail the intended checks.
- No Glue or AWS resource is required for local tests.

## `GLUE-020` — AWS foundation and EC2 repository workflow

Branch: `agent/hermes-codex/glue-020-aws-foundation`  
PR grouping: PR 3 only

### To-do

- [x] Create simple, non-overmodularized Terraform under `infrastructure/terraform/`.
- [x] Add provider constraints and lock file.
- [x] Create dedicated VPC, one subnet, route table, internet gateway, S3 gateway endpoint, and required security groups.
- [x] Create encrypted S3 bucket with public access blocked and lifecycle rules for temporary objects.
- [x] Create Secrets Manager secret resources without secret values.
- [x] Create least-privilege EC2 and Glue IAM roles/policies.
- [x] Create Amazon Linux EC2 with encrypted gp3 root disk, project tags, SSM access, Docker/Git bootstrap, and no inbound SSH.
- [x] Clone the public repository to `/opt/aws-glue-postgres-mongodb-lab` and record the checked-out Git commit SHA during each lab run.
- [x] Add `scripts/put-lab-secrets.sh`; generate and store values without output.
- [x] Add SSM-based database startup after secret values exist.
- [x] Add optional SSM-based deploy-key generation and instructions for write-enabled EC2 pushes.
- [x] Ensure the private deploy key never leaves EC2.
- [x] Implement `make doctor`, `make infra-init`, `make infra-plan`, `make infra-apply`, `make secrets-put`, and `make ec2-bootstrap`.
- [x] Keep Terraform in one understandable root configuration unless a small local module materially reduces repetition.
- [x] Add simple automated assertions or plan inspection instructions for forbidden public ingress and NAT Gateway absence; do not introduce a policy-as-code framework.
- [x] Complete `docs/runbook/00-PREREQUISITES.md` and `docs/runbook/01-DEPLOY-INFRASTRUCTURE.md` in the same PR.

### Acceptance

- `terraform fmt -check` and `terraform validate` pass.
- Plan contains only intended lab resources.
- No secret value appears in Terraform plan or state.
- EC2 is reachable through SSM and not SSH.
- EC2 clones the public repository and the run records the checked-out commit SHA.
- PostgreSQL and MongoDB are reachable from the Glue security group path, not from public inbound access.
- A destroy plan is reviewable.

## `GLUE-025` — Foundation teardown and persistent-volume rotation correction

Branch: `agent/hermes-codex/glue-025-foundation-cleanup`
PR grouping: PR 4 only

### To-do

- [x] Add an exact project/state/account/profile/Region/Git/plan-hash-bound destroy-plan workflow.
- [x] Require explicit approval and consume only the reviewed Terraform destroy plan.
- [x] Verify that current Terraform-managed foundation state is empty after destroy without broad service cleanup.
- [x] Add an SSM-based `make ec2-reset-data` that resets only the fixed Compose project's two containers and named volumes before reseeding and testing.
- [x] Direct secret rotation with existing named volumes to `ec2-reset-data`, not plain `ec2-bootstrap`.
- [x] Document the personal-account live-validation sequence, redaction rules, and foundation destroy procedure.
- [x] Add credential-free contract tests for fail-closed mutation gates and exact reset scope.

### Acceptance

- Destroy planning and execution reject ambient credential/Terraform overrides, require the default workspace, match active state lineage/serial to the exact local `terraform.tfstate`, and resolve the exact repository, Terraform root, personal account/principal, profile, `us-east-1`, Git SHA, operation type, and unchanged reviewed plan hash.
- `make destroy-lab` refuses to act without `APPROVE_LAB_DESTROY=1` and never substitutes an unreviewed `terraform destroy`.
- Post-destroy verification covers current Terraform-managed foundation resources only; final cross-service inventory remains `GLUE-060` work.
- Secret rotation against persistent databases removes only Compose project `aws-glue-postgres-mongodb-lab` services and its `postgres_data` and `mongodb_data` volumes before deterministic reseed/tests.
- No live AWS call, Docker start, resource creation, push, merge, or fabricated evidence occurs in this corrective implementation PR.
- At the PR #4 checkpoint, `GLUE-030` and later tasks remained `NOT STARTED`.

## `GLUE-030` — Glue connections, crawler, and Data Catalog

Branch: `agent/hermes-codex/glue-030-040-etl`  
PR grouping: PR 5 with `GLUE-040`

### To-do

- [x] Create the Glue Data Catalog database.
- [x] Create the PostgreSQL JDBC Glue connection using Secrets Manager and the lab VPC configuration.
- [x] Create the native MongoDB Glue connection using Secrets Manager and the same subnet/security topology.
- [x] Add only required Secrets Manager and S3 permissions to the Glue role.
- [x] Split MongoDB bootstrap administration from the connector-only secret so Glue cannot read root credentials.
- [x] Create a crawler restricted to `sales.orders` and `sales.order_items`.
- [x] Create an on-demand crawler invocation script.
- [x] Assert catalog tables and expected schemas after the crawl.
- [x] Upload Glue application artifacts to a documented lab S3 prefix. Avoid an artifact-release/versioning system; recording the Git SHA is sufficient.
- [x] Implement `make deploy` and `make crawl`.
- [x] Complete `docs/runbook/03-CONFIGURE-GLUE.md` in the same PR.

### Acceptance

- Both connections use the same subnet.
- Connection configuration contains no inline credential.
- Crawler creates exactly the intended source tables.
- Repeated crawler run does not create duplicate tables.
- No crawler schedule is created.
- Development acceptance uses Terraform mock-provider/static tests and fake-boundary script tests; actual connection and crawler behavior is user-run only and is not required PR evidence.

## `GLUE-040` — PySpark transformation and MongoDB load

Branch: `agent/hermes-codex/glue-030-040-etl`  
PR grouping: PR 5 with `GLUE-030`

### To-do

- [x] Create pure transformation functions under `src/glue_lab/transformations.py`.
- [x] Create a thin Glue entry point under `glue/jobs/postgres_orders_to_mongodb.py`.
- [x] Read both source tables through the catalog.
- [x] Filter soft-deleted rows.
- [x] Validate keys, relationships, quantity, and price before transformation.
- [x] Normalize customer name, email, status, and timestamps.
- [x] Calculate exact decimal line totals and order totals.
- [x] Embed and sort items.
- [x] Produce deterministic `_id` from `order_id`.
- [x] Write to MongoDB with the named Glue connection and `replaceDocument=true`.
- [x] Parameterize database, collection, connection names, and snapshot mode without accepting credentials as arguments.
- [x] Add unit tests for mapping, nesting, ordering, decimals, null/error behavior, soft deletes, and multiple orders.
- [x] Retain credential-free data-layer container smoke coverage in CI; Spark/database connector execution remains user-run.
- [x] Implement `make run` and a job-status waiter with timeout and failure-log pointer.
- [x] Complete `docs/runbook/04-RUN-MIGRATION.md` in the same PR.

### Acceptance

- Unit tests run without AWS credentials.
- Glue job does not collect the complete dataset to the driver.
- Invalid source data fails before target write.
- One valid order produces one correctly nested document.
- Credentials and full records do not appear in logs.
- Initial snapshots and unchanged-source reruns are supported. `replaceDocument=true` does not delete a previously emitted target document after a later source soft delete; changed-source deletion convergence is explicitly deferred to detection/resolution in `GLUE-050` without destructive pre-load or CDC.
- Development acceptance is credential-free unit/static/mock evidence. Running the Glue job and observing MongoDB output is user-run only and is not required PR evidence.

## `GLUE-050` — Reconciliation and rerun validation

Branch: `agent/hermes-codex/glue-050-060-validation`  
PR grouping: PR 6 with `GLUE-060`

### To-do

- [x] Build `validation/reconcile.py` with PostgreSQL and MongoDB readers.
- [x] Retrieve credentials from Secrets Manager at runtime without logging them.
- [x] Compare active order/document counts.
- [x] Compare active item/embedded-array counts.
- [x] Compare exact per-order totals.
- [x] Compare item order and normalized fixtures.
- [x] Verify soft-deleted records are absent.
- [x] Produce concise redacted JSON and console summaries.
- [x] Exit nonzero on any mismatch.
- [x] Run the Glue job twice against the same source.
- [x] Prove target count does not increase.
- [x] Modify one valid source order in a controlled test, rerun the snapshot, and prove the target document reflects the intended replacement behavior.
- [x] Change one previously emitted source order to soft-deleted, rerun, detect that `replaceDocument=true` does not delete the stale target document, and provide an explicit user-run resolution without claiming `GLUE-040` deletion convergence.
- [x] Implement `make validate` and `make rerun-test`.
- [x] Complete `docs/runbook/05-VALIDATE-AND-RERUN.md` in the same PR.

### Acceptance

- Credential-free reconciliation and rerun command contracts pass.
- A deliberate mismatch fixture produces a nonzero exit.
- Expected unchanged rerun, controlled replacement, stale-target detection, and explicit user-run resolution behavior are documented and covered by static, mock, and unit checks.
- Live Glue and connector execution is **user-run only**; contradictory results follow the documented troubleshooting path and become a separate issue/PR.

## `GLUE-060` — Runbook, cleanup, and release

Branch: `agent/hermes-codex/glue-050-060-validation`  
PR grouping: PR 6 with `GLUE-050`

### To-do

- [x] Review all runbooks against `DOCUMENTATION_STANDARD.md`; do not defer missing component instructions to README prose.
- [x] Complete `docs/runbook/06-DESTROY.md` and `docs/runbook/07-TROUBLESHOOTING.md`.
- [x] Document GitHub-to-EC2 clone and optional EC2 write workflow as an optional section, not a prerequisite for the core lab.
- [x] Add a simple `make cost-check` that inventories the lab's expected resources. Do not build a cost dashboard or depend on delayed Cost Explorer results.
- [x] Reuse the approval-gated `make destroy-lab` for the complete Terraform state and add final cross-service cleanup proof without weakening its exact project/plan binding.
- [x] Add `scripts/verify-destroyed.sh` for project-tagged resource checks.
- [x] Document manually removed resources, if any.
- [x] Run all credential-free command contracts from a clean checkout and record observed local/static/mock results.
- [x] Keep optional user-run release evidence separate from development acceptance.
- [x] Update README status and all roadmap tasks.

### Acceptance

- A clean Mac Mini can follow the linked runbooks without undocumented steps.
- Every runnable step contains prerequisites, exact commands, expected result, verification, repeat/reset behavior, and focused troubleshooting.
- Documentation does not assume prior AWS Glue, Terraform, PostgreSQL, MongoDB, or Docker knowledge.
- Credential-free clean-checkout checks and command contracts pass.
- User-run E2E, destroy, and post-destroy results are optional user-run release evidence, not requirements for `DONE`; when supplied, record them separately and redact them.
- No credential or live endpoint is present in repository history or PR evidence.

## `GLUE-070` — Improve prerequisite onboarding

Branch: `agent/hermes-codex/glue-070-prerequisite-usability`

PR grouping: one corrective documentation PR

### To-do

- [x] Explain the purpose of every Mac-side tool before installation.
- [x] Add exact Homebrew installation, shell setup, and verification guidance.
- [x] Explain GitHub's browser authentication prompts and credential storage.
- [x] Distinguish an AWS CLI profile name, authentication credentials, Region settings, and shell environment variables.
- [x] Document temporary browser authentication with `aws login`, including the personal root-user case, without requesting or storing credentials in the repository.
- [x] Retain IAM Identity Center as a separate authentication path and discourage long-lived root access keys.
- [x] Add exact optional Docker Desktop, Python 3.11, and Java 17 installation and first-launch instructions.
- [x] Expand expected results, pass conditions, and diagnose/correct/retry guidance for the prerequisite steps.
- [x] Keep all AWS commands labeled **User-run only** and preserve Docker as an optional local path.

### Acceptance

- A reader starting with a personal Mac and AWS Console login understands why each command is needed and what it changes.
- Authentication guidance does not ask the reader to paste credentials into the repository or expose account identifiers.
- Root Console authentication uses temporary `aws login` credentials; no root access-key creation is instructed.
- Optional tools do not become prerequisites for the core EC2 path.
- Documentation/static checks pass without AWS credentials or AWS calls.
- No infrastructure, application, or architecture file changes.

## `GLUE-080` — Standardize AWS CLI profile naming

Branch: `agent/hermes-codex/glue-080-profile-consistency`

PR grouping: one corrective documentation PR

### To-do

- [x] Use `personal-glue-lab` as the canonical AWS CLI profile name in every ordered runbook.
- [x] Replace the stale `personal-lab` exports in runbooks 03 and 04.
- [x] Preserve all AWS commands as **User-run only** and make no AWS calls.
- [x] Keep the correction limited to documentation and roadmap tracking.

### Acceptance

- Every file under `docs/runbook/` uses `personal-glue-lab` when naming the personal AWS CLI profile.
- No ordered runbook contains the stale profile name `personal-lab`.
- Documentation and governance checks pass without AWS credentials or AWS calls.
- No infrastructure, application, script, test, or architecture file changes.
