# 04 — Run the Snapshot Migration

Owner: `GLUE-040`  
Status: implementation complete

> **User-run only:** Every AWS, SSM, Glue, and MongoDB command in this runbook is run by the user after cloning completed reviewed code. Agents must never request or use AWS credentials. No agent-run live AWS evidence is required; development acceptance uses static/mock/Terraform/unit/container checks. A failure in this user-run lab becomes a separate issue/PR.

The Glue 5.1 job reads `orders` and `order_items` from the Data Catalog, validates active source rows, and writes one nested MongoDB document per active order through the named MongoDB connection. It never accepts credential arguments, logs full records, or collects the full dataset to the driver.

For order `1001`, `_id` is deterministically `1001`; customer name/email/status are trimmed and normalized; timestamps are formatted in UTC; active items are sorted by `lineNumber`; and `lineTotal`/`orderTotal` remain Spark decimals. Soft-deleted orders/items are omitted. An active order with zero active items fails validation deterministically instead of emitting an empty document.

The supported contract is the initial snapshot and unchanged-source reruns. `replaceDocument=true` does not delete an already-emitted target document when its source order is later soft-deleted. Changed-source deletion convergence is outside `GLUE-040`; `GLUE-050` must detect and explicitly resolve that stale target without adding destructive pre-load or CDC here.

## Step 1 — Confirm migration prerequisites

**Purpose**

Require the reviewed artifacts, exact catalog, healthy database containers, and non-secret runtime inputs before starting the only Glue job.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- The user completed runbooks 01–03.
- `make deploy` recorded the intended Git SHA.
- `make crawl` passed the exact two-table assertion.
- PostgreSQL and MongoDB are healthy on EC2.
- Terraform state contains `glue_job_name`, `mongodb_glue_connection_name`, and `database_instance_id` outputs.

**Inputs**

```bash
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
```

`AWS_PROFILE` identifies the user's personal lab profile. `AWS_REGION` must remain `us-east-1`.

**Command**

```bash
test -n "$AWS_PROFILE" && test "$AWS_REGION" = "us-east-1"
terraform -chdir=infrastructure/terraform output -raw glue_job_name >/dev/null
terraform -chdir=infrastructure/terraform output -raw mongodb_glue_connection_name >/dev/null
printf '%s\n' 'migration prerequisites: PASS'
```

**Expected result**

The command exits 0 and prints `migration prerequisites: PASS` without exposing credential or connection-property values.

**Verify**

```bash
make format-check && make lint && make unit-test && make terraform-check
```

Pass: all credential-free checks exit 0. These are development-safe checks and make no AWS call. They do not claim the user-run migration succeeded.

**Repeat, reset, or rollback**

Safe to repeat. No AWS operation occurs in this step.

**If it fails**

If an output is missing, return to runbook 01 and use the reviewed user-run Terraform workflow. If unit tests fail, stop and file a separate issue/PR; do not run Glue with failing transformation tests.

**Next**

Start the bounded job waiter.

## Step 2 — Run and wait for the snapshot job

**Purpose**

Start the one unscheduled Glue job and wait at most twenty minutes for a terminal result.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 1 passes and no other run of this one-concurrency job is active.

**Inputs**

`JOB_TIMEOUT_SECONDS` defaults to `1200` and cannot exceed `3600`; `JOB_POLL_SECONDS` defaults to `15` and cannot exceed `60`. The job's database, table, connection, collection, and snapshot-mode arguments come from Terraform and contain no credentials.

**Command — User-run only**

```bash
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
APPROVE_GLUE_RUN=1 JOB_TIMEOUT_SECONDS=1200 JOB_POLL_SECONDS=15 make run
```

**Expected result**

Before starting Glue, the command requires `glue/artifacts/GIT_SHA` to equal the clean local `HEAD`; a missing or mismatched marker fails without printing either SHA. It then exits 0 and prints `run: PASS (Glue job succeeded; identifiers redacted)`. A source validation error occurs before target write. Logs contain source counts, transformed count, bounded phase durations/outcomes, and no credentials or full records.

**Verify — User-run only**

```bash
JOB_NAME="$(terraform -chdir=infrastructure/terraform output -raw glue_job_name)"
aws glue get-job-runs --job-name "$JOB_NAME" --max-results 1 \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'JobRuns[0].{State:JobRunState,GlueVersion:GlueVersion,Workers:NumberOfWorkers,WorkerType:WorkerType}' \
  --output table
unset JOB_NAME
```

Pass: state is `SUCCEEDED`, Glue version is `5.1`, workers is `2`, and worker type is `G.1X`.

**Repeat, reset, or rollback**

The job supports an initial full snapshot and unchanged-source reruns. Deterministic `_id` and `replaceDocument=true` request replacement semantics; the user proves unchanged-source count stability later in runbook 05. It does not delete a stale target after a later source soft delete. Do not clear the collection here; `GLUE-050` owns detection and explicit resolution. Terraform destroy is the AWS rollback.

**If it fails**

- `ConcurrentRunsExceededException`: wait for the current run to finish, then repeat.
- Missing catalog table: rerun user-owned `make crawl` from runbook 03.
- Validation error mentioning null/duplicate key, duplicate business key, orphan, quantity, price, or empty items: correct only the synthetic source fixture in a separate issue/PR; do not bypass validation.
- MongoDB authentication/network failure: confirm runbook 02 secret/reset state and Terraform security-group references; do not add public ingress.
- Serialization/type failure: preserve the redacted exception and open a separate issue/PR.
- The waiter always prints the failure-log pointer `aws logs tail /aws-glue/jobs/error --since 1h --follow`; run it only with the user profile and do not publish secrets or full records.

**Next**

Open a Systems Manager session to inspect a redacted target summary.

## Step 3 — Open the database-host session

**Purpose**

Reach the private MongoDB container without SSH or public database ingress.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 2 passes and the Session Manager plugin is installed as described in runbook 00.

**Inputs**

Uses the same personal profile and Region.

**Command — User-run only**

```bash
INSTANCE_ID="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"
aws ssm start-session --target "$INSTANCE_ID" --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

**Expected result**

An interactive Session Manager shell opens on the one lab EC2 host. No inbound port is opened.

**Verify — User-run only**

```bash
pwd
```

Pass: the command runs inside the Session Manager shell. The exact starting directory may vary.

**Repeat, reset, or rollback**

Type `exit` to close the session. Safe to open another session later.

**If it fails**

Run the runbook 02 SSM diagnostics from the Mac. Do not add SSH or public ingress.

**Next**

Run Step 4 inside this session.

## Step 4 — Inspect a redacted MongoDB summary

**Purpose**

Confirm the target has documents and inspect only the synthetic fields needed to recognize normalization, item ordering, decimal totals, and snapshot metadata.

**Run from**

`EC2 through Systems Manager Session Manager`

**Prerequisites**

Step 3 opened the session, the `mongodb` Compose service is running, and `command -v jq` exits `0`. Terraform user data installs `jq`; if it is absent, stop and re-run the implemented infrastructure/bootstrap path rather than pasting secrets into another tool.

**Inputs**

No value is typed by the user. The EC2 role retrieves the fixed lab secret into shell memory; the command unsets it immediately afterward.

**Command — User-run only**

```bash
(
set -euo pipefail
set +x
cleanup_mongo_secret_vars() {
  unset SECRET_JSON MONGO_USER MONGO_PASSWORD AUTH_JSON MONGO_CONTAINER
}
trap cleanup_mongo_secret_vars EXIT
SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id /aws-glue-postgres-mongodb-lab/mongodb-glue \
  --region us-east-1 --query SecretString --output text)"
MONGO_USER="$(jq -r .username <<<"$SECRET_JSON")"
MONGO_PASSWORD="$(jq -r .password <<<"$SECRET_JSON")"
AUTH_JSON="$(jq -cn --arg username "$MONGO_USER" --arg password "$MONGO_PASSWORD" \
  '{user:$username,pwd:$password}')"
unset SECRET_JSON
MONGO_CONTAINER="$(docker ps \
  --filter label=com.docker.compose.project=aws-glue-postgres-mongodb-lab \
  --filter label=com.docker.compose.service=mongodb --format '{{.ID}}')"
test -n "$MONGO_CONTAINER"
{
  printf 'const credentials = %s;\n' "$AUTH_JSON"
  cat <<'MONGOSH'
if (!db.auth(credentials)) {
  throw new Error("MongoDB authentication failed");
}
const count = db.orders.countDocuments({});
const sample = db.orders.aggregate([
  {$match: {_id: 1001}},
  {$limit: 1},
  {$project: {_id: 1, status: 1, customerEmail: "$customer.email",
    lineNumbers: "$items.lineNumber", lineTotals: "$items.lineTotal",
    orderTotal: 1, migration: 1}}
]).toArray();
print(JSON.stringify({count: count, sample: sample}));
MONGOSH
} | docker exec -i "$MONGO_CONTAINER" mongosh --quiet migration_lab
cleanup_mongo_secret_vars
trap - EXIT
)
```

**Expected result**

One redacted JSON object prints. `count` is greater than zero. The sample for `_id: 1001` has lowercase trimmed email, uppercase status, ascending line numbers, exact decimal totals, and migration mode `snapshot`. No password or complete source/target record is printed.

**Verify — User-run only**

```bash
test -z "${MONGO_PASSWORD:-}" && test -z "${MONGO_USER:-}" && \
  test -z "${AUTH_JSON:-}" && printf '%s\n' 'temporary secret variables removed: PASS'
```

Pass: `temporary secret variables removed: PASS` prints. Type `exit` to close the SSM session.

**Repeat, reset, or rollback**

Read-only and safe to repeat. Do not write, delete, or repair target documents from this inspection step. Runbook 05 owns reconciliation and rerun proof.

**If it fails**

- Empty container ID: run `docker ps --filter label=com.docker.compose.project=aws-glue-postgres-mongodb-lab` and return to runbook 02.
- Authentication failure: exit, follow the runbook 02 secret-rotation/reset procedure, rerun the user-owned migration, and retry.
- Count is zero or sample missing after a successful Glue status: preserve only the redacted summary and job state, then open a separate issue/PR.
- Unsorted items or incorrect totals/normalization: do not edit MongoDB manually; file a separate issue/PR with the synthetic `_id` and redacted fields.

**Next**

Continue to [05 — Validate and rerun](05-VALIDATE-AND-RERUN.md). That roadmap task remains not started, so its operational targets still fail clearly until implemented.
