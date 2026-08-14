# Acceptance and Test Plan

## Acceptance ownership

Development agents must never request, obtain, or use AWS credentials and must never execute AWS commands or live Terraform operations. Development acceptance is complete with credential-free static checks, mocked service boundaries, Terraform validation/mock-provider tests, Python/Spark unit tests, and local container tests. No agent-run live AWS evidence is required.

Items explicitly labeled **USER-RUN ONLY** are a post-clone lab checklist for the user, not PR gates. A failure discovered there must be filed as a separate issue/PR.

## 0. Documentation usability and lab simplicity

- [ ] README is a concise introduction, architecture summary, sequence, and runbook index—not a competing abbreviated manual.
- [ ] Ordered runbooks cover prerequisites through destruction.
- [ ] Every runnable step identifies where it runs.
- [ ] Every runnable step has observable prerequisites.
- [ ] Every required input and placeholder is defined before use.
- [ ] Every command is complete and copyable.
- [ ] Every command states the expected result.
- [ ] Every action has a verification command and explicit pass condition.
- [ ] Rerun, reset, or rollback behavior is documented.
- [ ] Likely failures include diagnosis, correction, and retry commands.
- [ ] Observed credential-free command-contract execution covers the branch that introduced each instruction; user-run AWS commands remain an optional separate checklist and are never inferred as passed.
- [ ] No owning task is `DONE` while its runbook contains implementation markers or `TODO` instructions.
- [ ] Optional local Docker and EC2-push paths are clearly separated from the core lab.
- [ ] No multi-environment framework, remote Terraform backend, deployment pipeline, custom AMI, HA topology, production PKI, autoscaling, dashboard platform, or policy-as-code framework was added.
- [ ] Troubleshooting does not introduce public database access or a NAT Gateway.

## 1. Repository safety

- [ ] Repository is public by intentional decision.
- [ ] No secret, token, key, credentialed URI, live public IP, Terraform state, or plan is tracked.
- [ ] Secret scanner passes across the full Git history.
- [ ] `.gitignore` covers all generated sensitive artifacts.
- [ ] Fixtures are synthetic and contain no work/client data.
- [ ] PRs cannot be merged automatically by Hermes or Codex.

## 2. Local data layer

- [ ] Docker Compose configuration validates.
- [ ] PostgreSQL health check passes.
- [ ] MongoDB health check passes.
- [ ] Schema and seed initialization are deterministic.
- [ ] Source constraints prevent invalid production fixtures.
- [ ] Failure fixtures can be invoked independently.
- [ ] Local teardown removes only project containers/volumes.

## 3. Infrastructure

- [ ] Terraform formatting and validation pass.
- [ ] Terraform plan is reviewed before apply.
- [ ] All supported resources have required project tags.
- [ ] No NAT Gateway exists.
- [ ] No public inbound rule permits ports 22, 5432, or 27017.
- [ ] EC2 is managed through SSM.
- [ ] Root volume and S3 bucket are encrypted.
- [ ] S3 public access block is enabled.
- [ ] Secret values are absent from Terraform configuration, plan, state, and output.
- [ ] IAM permissions are limited to lab resources and required service actions.
- [ ] EC2 records the Git commit SHA used for the lab run.

## 4. Glue metadata and connections

- [ ] PostgreSQL and MongoDB Glue connections use the same subnet.
- [ ] Glue security group has required self-referencing communication.
- [ ] PostgreSQL connection succeeds.
- [ ] MongoDB connection succeeds.
- [ ] Crawler creates only the two intended catalog tables.
- [ ] Repeated crawler run is stable.
- [ ] Glue job code and package are uploaded to the documented lab S3 prefix.
- [ ] No scheduled crawler or job exists.

## 5. Transformation unit tests

- [ ] `order_id` maps to deterministic `_id`.
- [ ] Customer fields form the expected nested object.
- [ ] Names are trimmed and combined correctly.
- [ ] Emails are trimmed and lowercased.
- [ ] Status is trimmed and uppercased.
- [ ] Timestamps normalize to UTC.
- [ ] Deleted orders are excluded.
- [ ] Deleted items are excluded.
- [ ] Items embed under the correct order.
- [ ] Items sort by `lineNumber` ascending.
- [ ] Line totals retain exact decimal behavior.
- [ ] Order totals equal exact sum of line totals.
- [ ] Null primary key fails.
- [ ] Null deletion flags fail before soft-delete filtering.
- [ ] Null child `order_id` or `line_number` fails.
- [ ] Null or negative quantity fails.
- [ ] Null price and required order/item values fail.
- [ ] Duplicate business key fails.
- [ ] Orphan item fails.
- [ ] Zero/negative quantity fails.
- [ ] Negative price fails.
- [ ] Empty active item set follows the documented rule.

## 6. End-to-end migration

- [ ] Glue crawler succeeds.
- [ ] Glue job succeeds with two `G.1X` workers.
- [ ] CloudWatch logs contain run ID, counts, timings, and outcome.
- [ ] Logs contain no secret or full sensitive record.
- [ ] Target contains one document per active order.
- [ ] Target document structure matches `DESIGN.md`.

## 7. Reconciliation invariants

Let:

- `O` = count of active PostgreSQL orders;
- `I` = count of active items belonging to active orders;
- `D` = count of MongoDB order documents;
- `A` = sum of all MongoDB `items` array lengths.

Required:

```text
O = D
I = A
```

For every active `order_id`:

```text
source active item count = target items length
source exact total       = target orderTotal
source key               = target _id
```

Additional checks:

- [ ] No target document lacks a source order.
- [ ] No active source order lacks a target document.
- [ ] No deleted entity appears in target.
- [ ] Expected normalization fixtures match exactly.
- [ ] Reconciliation exits nonzero after an intentional mismatch.
- [ ] Reconciliation output is redacted and machine-readable.

## 8. User-run-only rerun behavior (optional lab evidence)

The supported `GLUE-040` contract is the initial snapshot and unchanged-source reruns. `replaceDocument=true` does not delete an already-emitted target document when its source order later becomes soft-deleted. Changed-source deletion convergence must be detected and explicitly resolved in `GLUE-050`; it is not provided by destructive pre-load or CDC.

- [ ] Capture target count and selected document hashes after run 1.
- [ ] Run the identical Glue job again.
- [ ] Target count remains unchanged.
- [ ] No duplicate `_id` exists.
- [ ] Unchanged business content remains equivalent.
- [ ] Apply one controlled source update.
- [ ] Run the snapshot job again.
- [ ] Corresponding MongoDB document reflects the controlled update.
- [ ] Connector behavior may be recorded later as user-supplied redacted evidence, separately from development acceptance.
- [ ] Active-on-run-1/deleted-on-run-2 leaves a stale target that reconciliation detects and the user-run resolution handles explicitly.

## 9. User-run-only destruction and cost (optional lab evidence)

- [ ] `make cost-check` inventories the expected lab resources.
- [ ] `make destroy-lab` verifies project and working directory before destroy.
- [ ] Terraform destroy completes successfully.
- [ ] Post-destroy verification finds no known project-tagged billable resources.
- [ ] Optional GitHub deploy key is removed when the EC2 write workflow is retired.
- [ ] Temporary local secret material is absent.
- [ ] README warns against leaving resources running overnight.
- [ ] Destroy runbook states that stopping EC2 alone is not sufficient cleanup.

## 10. Required development evidence

The implementation PR includes observed credential-free results for:

```bash
make format-check
make lint
make unit-test
make compose-check
make terraform-check
bash -n scripts/*.sh
git diff --check
```

Static/mock versus local-container scope, skipped checks, and limitations must be explicit. No AWS credential, AWS call, live Terraform plan/apply, connection test, crawler/job run, SSM action, Secrets Manager action, resource creation, or teardown validation is permitted for agent development.

## 11. User-run-only lab evidence

After cloning completed reviewed code, the user may run the operational sequence:

```bash
make doctor
make infra-plan
APPROVE_LAB_APPLY=1 make infra-apply
APPROVE_LAB_SECRETS=1 make secrets-put
make ec2-bootstrap
APPROVE_GLUE_DEPLOY=1 make deploy
APPROVE_GLUE_CRAWL=1 make crawl
APPROVE_GLUE_RUN=1 make run
APPROVE_GLUE_VALIDATE=1 make validate
APPROVE_GLUE_RERUN=1 make rerun-test
APPROVE_LAB_COST_CHECK=1 make cost-check
make destroy-plan
APPROVE_LAB_DESTROY=1 make destroy-lab
```

These commands are **USER-RUN ONLY**, are not agent development gates, and must not be represented as passed without user-supplied redacted output. The user records who followed the ordered runbooks and any corrections discovered. A failure becomes a separate issue/PR.
