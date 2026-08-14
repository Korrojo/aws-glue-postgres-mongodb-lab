# Roadmap and To-Do

## Status values

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `PR OPEN`
- `DONE`
- `MERGED — PENDING LIVE VALIDATION`

Only one task may be `IN PROGRESS` unless Hermes proves that file ownership and dependencies do not overlap.

## Summary

| Task | Status | PR | Depends on | Outcome |
|---|---|---|---|---|
| `GLUE-000` | DONE | [#1](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/1) | — | Governance and repository skeleton |
| `GLUE-010` | DONE | [#2](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/2) | `GLUE-000` | Containerized source/target and fixtures |
| `GLUE-020` | MERGED — PENDING LIVE VALIDATION | [#3](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/3) | `GLUE-010` | Disposable AWS foundation and EC2 workflow |
| `GLUE-025` | PR OPEN | [#4](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/4) | `GLUE-020` | Foundation teardown and persistent-volume rotation correction |
| `GLUE-030` | NOT STARTED | — | `GLUE-025` | Glue networking, connections, crawler, catalog |
| `GLUE-040` | NOT STARTED | — | `GLUE-030` | PySpark transformation and MongoDB load |
| `GLUE-050` | NOT STARTED | — | `GLUE-040` | Reconciliation and rerun validation |
| `GLUE-060` | NOT STARTED | — | `GLUE-050` | Runbook, cleanup proof, final release |

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
- `GLUE-030` and later tasks remain `NOT STARTED`.

## `GLUE-030` — Glue connections, crawler, and Data Catalog

Branch: `agent/hermes-codex/glue-030-040-etl`  
PR grouping: PR 5 with `GLUE-040`

### To-do

- [ ] Create the Glue Data Catalog database.
- [ ] Create the PostgreSQL JDBC Glue connection using Secrets Manager and the lab VPC configuration.
- [ ] Create the native MongoDB Glue connection using Secrets Manager and the same subnet/security topology.
- [ ] Add only required Secrets Manager and S3 permissions to the Glue role.
- [ ] Create a crawler restricted to `sales.orders` and `sales.order_items`.
- [ ] Create an on-demand crawler invocation script.
- [ ] Assert catalog tables and expected schemas after the crawl.
- [ ] Upload Glue application artifacts to a documented lab S3 prefix. Avoid an artifact-release/versioning system; recording the Git SHA is sufficient.
- [ ] Implement `make deploy` and `make crawl`.
- [ ] Complete `docs/runbook/03-CONFIGURE-GLUE.md` in the same PR.

### Acceptance

- Both connections use the same subnet.
- Connection configuration contains no inline credential.
- Crawler creates exactly the intended source tables.
- Repeated crawler run does not create duplicate tables.
- No crawler schedule is created.

## `GLUE-040` — PySpark transformation and MongoDB load

Branch: `agent/hermes-codex/glue-030-040-etl`  
PR grouping: PR 5 with `GLUE-030`

### To-do

- [ ] Create pure transformation functions under `src/glue_lab/transformations.py`.
- [ ] Create a thin Glue entry point under `glue/jobs/postgres_orders_to_mongodb.py`.
- [ ] Read both source tables through the catalog.
- [ ] Filter soft-deleted rows.
- [ ] Validate keys, relationships, quantity, and price before transformation.
- [ ] Normalize customer name, email, status, and timestamps.
- [ ] Calculate exact decimal line totals and order totals.
- [ ] Embed and sort items.
- [ ] Produce deterministic `_id` from `order_id`.
- [ ] Write to MongoDB with the named Glue connection and `replaceDocument=true`.
- [ ] Parameterize database, collection, connection names, and snapshot mode without accepting credentials as arguments.
- [ ] Add unit tests for mapping, nesting, ordering, decimals, null/error behavior, soft deletes, and multiple orders.
- [ ] Add an integration smoke test that uses the real containers where feasible.
- [ ] Implement `make run` and a job-status waiter with timeout and failure-log pointer.
- [ ] Complete `docs/runbook/04-RUN-MIGRATION.md` in the same PR.

### Acceptance

- Unit tests run without AWS credentials.
- Glue job does not collect the complete dataset to the driver.
- Invalid source data fails before target write.
- One valid order produces one correctly nested document.
- Credentials and full records do not appear in logs.

## `GLUE-050` — Reconciliation and rerun validation

Branch: `agent/hermes-codex/glue-050-060-validation`  
PR grouping: PR 6 with `GLUE-060`

### To-do

- [ ] Build `validation/reconcile.py` with PostgreSQL and MongoDB readers.
- [ ] Retrieve credentials from Secrets Manager at runtime without logging them.
- [ ] Compare active order/document counts.
- [ ] Compare active item/embedded-array counts.
- [ ] Compare exact per-order totals.
- [ ] Compare item order and normalized fixtures.
- [ ] Verify soft-deleted records are absent.
- [ ] Produce concise redacted JSON and console summaries.
- [ ] Exit nonzero on any mismatch.
- [ ] Run the Glue job twice against the same source.
- [ ] Prove target count does not increase.
- [ ] Modify one valid source order in a controlled test, rerun the snapshot, and prove the target document reflects the intended replacement behavior.
- [ ] Implement `make validate` and `make rerun-test`.
- [ ] Complete `docs/runbook/05-VALIDATE-AND-RERUN.md` in the same PR.

### Acceptance

- All checks in `ACCEPTANCE_CRITERIA.md` pass.
- Deliberate mismatch produces a nonzero exit.
- Second run is proven, not inferred.
- Connector rerun behavior is documented from observed output.

## `GLUE-060` — Runbook, cleanup, and release

Branch: `agent/hermes-codex/glue-050-060-validation`  
PR grouping: PR 6 with `GLUE-050`

### To-do

- [ ] Review all runbooks against `DOCUMENTATION_STANDARD.md`; do not defer missing component instructions to README prose.
- [ ] Complete `docs/runbook/06-DESTROY.md` and `docs/runbook/07-TROUBLESHOOTING.md`.
- [ ] Document GitHub-to-EC2 clone and optional EC2 write workflow as an optional section, not a prerequisite for the core lab.
- [ ] Add a simple `make cost-check` that inventories the lab's expected resources. Do not build a cost dashboard or depend on delayed Cost Explorer results.
- [ ] Reuse the approval-gated `make destroy-lab` for the complete Terraform state and add final cross-service cleanup proof without weakening its exact project/plan binding.
- [ ] Add `scripts/verify-destroyed.sh` for project-tagged resource checks.
- [ ] Document manually removed resources, if any.
- [ ] Run the complete lab from a clean checkout.
- [ ] Capture redacted final evidence in the PR.
- [ ] Update README status and all roadmap tasks.

### Acceptance

- A clean Mac Mini can follow the linked runbooks without undocumented steps.
- Every runnable step contains prerequisites, exact commands, expected result, verification, repeat/reset behavior, and focused troubleshooting.
- Documentation does not assume prior AWS Glue, Terraform, PostgreSQL, MongoDB, or Docker knowledge.
- Full E2E run passes.
- `terraform destroy` succeeds.
- Post-destroy verification finds no known project-tagged billable resource.
- No credential or live endpoint is present in repository history or PR evidence.
