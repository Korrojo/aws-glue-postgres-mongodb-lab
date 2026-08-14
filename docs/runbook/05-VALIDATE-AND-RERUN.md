# 05 — Reconcile and Test Rerun Behavior

Owner: `GLUE-050`  
Status: implementation complete

> **User-run only:** Every AWS, SSM, Glue, PostgreSQL, and MongoDB operation in this runbook is executed only by the user from a completed reviewed clone. Agents never request or use AWS credentials and never run these targets. Credential-free unit and fake-boundary tests are development acceptance; user-run output is optional evidence and must be redacted.

Order count alone is insufficient: one order can contain the wrong items, wrong exact total, wrong order, or unnormalized values while counts still agree. `validation/reconcile.py` therefore compares active order/document count, active item/embedded count, keys, per-order item count and exact `Decimal` totals, line ordering, normalized customer/status/timestamps, migration metadata, and deleted entities. It projects at most 100 orders and 1,000 items, uses only Python's standard library, and never emits a full record.

The EC2 reader retrieves only `/aws-glue-postgres-mongodb-lab/postgres` and `/aws-glue-postgres-mongodb-lab/mongodb-glue` at runtime. Credentials travel through process memory and stdin to `psql`/`mongosh`; they never appear in command arguments or output. The exact Compose identities are `aws-glue-postgres-mongodb-lab-postgres-1` and `aws-glue-postgres-mongodb-lab-mongodb-1`.

## Step 1 — Confirm the reviewed validation prerequisites

**Purpose**

Stop before AWS if the checkout, local tests, deployed revision, or personal-profile inputs are not ready.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Runbooks 00–04 completed successfully.
- The latest Glue run succeeded.
- PostgreSQL and MongoDB are healthy on the one SSM-managed EC2 host.
- The exact local Terraform state from the apply remains present.
- The repository is clean and checked out at the deployed reviewed revision.

**Inputs**

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
unset AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_ROLE_SESSION_NAME
unset AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
unset AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
unset AWS_ENDPOINT_URL
unset TF_WORKSPACE TF_DATA_DIR TF_CLI_ARGS TF_CLI_ARGS_plan TF_CLI_ARGS_apply
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
```

`AWS_PROFILE` is the user's intended personal profile. Any `AWS_ENDPOINT_URL_*` variable must also be unset; the scripts reject even an empty endpoint override.

**Command**

```bash
test "$(pwd -P)" = "$(git rev-parse --show-toplevel)"
test -z "$(git status --short)"
test -f infrastructure/terraform/terraform.tfstate
make format-check && make lint && make unit-test
```

**Expected result**

Every command exits `0`; the credential-free suite includes exact reconciliation and fake service-boundary tests. No AWS call occurs in this step.

**Verify**

```bash
test "$(terraform -chdir=infrastructure/terraform workspace show)" = default
test "$(terraform -chdir=infrastructure/terraform output -raw aws_region)" = us-east-1
```

Pass: both tests exit `0` without printing state, account, endpoint, or credentials.

**Repeat, reset, or rollback**

Safe to repeat. A dirty checkout, missing state, wrong workspace, wrong account, or wrong Region is a hard stop; do not bypass the guard.

**If it fails**

Use `git status --short` for checkout drift and `terraform -chdir=infrastructure/terraform workspace show` for workspace drift. Return to the exact reviewed clone/state rather than reconstructing or overriding identity.

**Next**

Run bounded reconciliation.

## Step 2 — Reconcile source and target

**Purpose**

Run the EC2-side readers and pure reconciliation core, retaining only a private redacted JSON result.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 1 passes; the database containers are healthy; the connector secret values exist; no unrelated Glue run is active.

**Inputs**

`APPROVE_GLUE_VALIDATE=1` explicitly approves this bounded user-run SSM/database-read operation. Optional waiter inputs are `SSM_TIMEOUT_SECONDS` (default `900`, maximum `1800`) and `SSM_POLL_SECONDS` (default `10`, maximum `60`).

**Command — User-run only**

```bash
APPROVE_GLUE_VALIDATE=1 SSM_TIMEOUT_SECONDS=900 SSM_POLL_SECONDS=10 \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make validate
```

**Expected result**

The command exits `0` only when the EC2 checkout is clean and its `HEAD` exactly matches the clean reviewed Mac checkout. It then prints a one-line JSON object containing only schema version, pass/fail, four counts, mismatch categories, and mismatch count, followed by `validate: PASS`. On EC2 it writes `/var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json` in a mode-`0700` directory with file mode `0600`.

**Verify — User-run only**

```bash
INSTANCE_ID="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"
aws ssm start-session --target "$INSTANCE_ID" --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

Inside the SSM session:

```bash
sudo -u ec2-user test "$(stat -c '%a' /var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json)" = 600
sudo -u ec2-user python3 -m json.tool /var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json
exit
```

Pass: `passed` is `true`, `mismatch_categories` is empty, and the artifact contains no secret, URI, account ID, ARN, endpoint, full order, email, SKU, or key.

**Repeat, reset, or rollback**

Safe to repeat against unchanged data; the private artifact is replaced atomically in scope. No source or target mutation occurs.

**If it fails**

- `boundary_error`: confirm both exact containers with the runbook 02 health check and confirm the two connector secrets retain their documented schemas; never paste a secret into a command.
- `active_order_count`, `active_item_count`, or key categories: inspect the latest Glue job state and rerun the snapshot only after identifying the source/target phase.
- `order_total`, `line_total`, `line_ordering`, or `normalization`: stop and preserve only the category/count summary; do not publish projected records.
- `stale_target` with `deleted_order_present`: use the explicit targeted resolution exercised in Step 3, never a collection-wide preload.

See [07 — Troubleshooting](07-TROUBLESHOOTING.md) for diagnostic commands.

**Next**

Prove unchanged rerun, replacement, deletion limitation, targeted resolution, and reset.

## Step 3 — Run the bounded rerun proof

**Purpose**

Prove, rather than infer, five behaviors: an unchanged second run has the same count/hash; one controlled fixture update replaces its document; active order `1003` becoming soft-deleted leaves a stale target; reconciliation fails nonzero and detects it; deleting only target `_id=1003` resolves it; and the fixture/target return to the baseline.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 2 passes. The reviewed Glue artifact matches clean local `HEAD`. The job has no concurrent run. Only synthetic fixture IDs `1001`, `1003`, and item `5002` are used.

**Inputs**

`APPROVE_GLUE_RERUN=1` approves the fixed fixture operations and repeated Glue runs. The script internally supplies `APPROVE_GLUE_RUN=1` to the already guarded job runner. Waiter limits are the same bounded SSM/job limits documented earlier.

**Command — User-run only**

```bash
APPROVE_GLUE_RERUN=1 JOB_TIMEOUT_SECONDS=1200 JOB_POLL_SECONDS=15 \
SSM_TIMEOUT_SECONDS=900 SSM_POLL_SECONDS=10 \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make rerun-test
```

**Expected result**

Stable phase labels end in:

```text
unchanged_second_run: PASS
controlled_replacement: PASS
stale_target_detection: PASS
targeted_stale_resolution: PASS
reset: PASS
rerun-test: PASS (unchanged, replacement, stale detection/resolution, reset)
```

The unchanged comparison uses only document/item counts plus a SHA-256 of bounded projected business data. The controlled update changes order `1001` status and item `5002` quantity, then reconciliation proves replacement. The soft-delete phase deliberately observes reconciliation exit `1` with `stale_target` and `deleted_order_present`; the orchestration accepts that one expected failure only after inspecting the redacted artifact. Resolution executes exactly `deleteOne({_id: 1003})`. It never clears the collection, performs a destructive preload, or claims CDC/deletion convergence.

**Verify — User-run only**

```bash
APPROVE_GLUE_VALIDATE=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make validate
```

Pass: final reconciliation exits `0`, proving the reset restored source `1001`/`1003` and the target baseline. A second unchanged proof does not increase document count or introduce duplicate `_id` values.

**Repeat, reset, or rollback**

Safe to repeat after a successful run. The first phase always resets the two fixed source fixtures and runs Glue to establish a known baseline. If the script stops, do not improvise SQL or MongoDB commands; use Step 4.

**If it fails**

- Glue timeout/failure: follow runbook 04 without changing fixtures further.
- Unchanged hash differs: stop; rerun behavior contradicted the expected connector contract. Preserve only redacted counts/hashes and file a separate issue/PR.
- Controlled hash does not change: inspect the latest job state and connector replacement behavior; do not add another connector.
- Expected stale mismatch is absent: stop and record the redacted categories; the connector behavior requires a design decision.
- Targeted deletion count is not exactly one: the script fails closed. Do not broaden the deletion.

**Next**

Use the reset path only if Step 3 did not finish; otherwise proceed to destroy.

## Step 4 — Recover an interrupted rerun proof

**Purpose**

Return only the fixed synthetic fixtures and deterministic target documents to their baseline after an interrupted proof.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

The cause of the interruption is corrected, the same reviewed checkout/state/profile/Region remain selected, and no Glue run is active.

**Inputs**

The same explicit rerun approval and bounded waiter inputs from Step 3.

**Command — User-run only**

```bash
APPROVE_GLUE_RERUN=1 JOB_TIMEOUT_SECONDS=1200 JOB_POLL_SECONDS=15 \
SSM_TIMEOUT_SECONDS=900 SSM_POLL_SECONDS=10 \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make rerun-test
```

**Expected result**

The orchestration begins with `phase=reset fixtures_to_known_baseline`, restores source `1001` and `1003`, and runs the full proof. It exits `0` only after final reconciliation and baseline fingerprint equality.

**Verify — User-run only**

```bash
APPROVE_GLUE_VALIDATE=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make validate
```

Pass: the command exits `0` with empty mismatch categories.

**Repeat, reset, or rollback**

Repeat only after correcting the reported phase. If deterministic reset itself fails, stop and destroy/rebuild through the reviewed Terraform workflow; never truncate PostgreSQL, clear MongoDB, or add CDC.

**If it fails**

Follow the exact failing phase in [07 — Troubleshooting](07-TROUBLESHOOTING.md). Preserve category/count/hash output only. A later user-run defect is separate issue/PR work, not fabricated development evidence.

**Next**

Proceed to [06 — Destroy the Lab](06-DESTROY.md).
