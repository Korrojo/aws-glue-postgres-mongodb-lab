# 03 — Configure and Verify AWS Glue

Owner: `GLUE-030`; usability correction by `GLUE-100`
Status: implementation complete

> **User-run only:** Every AWS command in this runbook is run by the user after cloning completed reviewed code. Agents must never request or use AWS credentials. No agent-run live AWS evidence is required; development acceptance uses static/mock/Terraform/unit/container checks. A failure in this user-run lab becomes a separate issue/PR.

A Glue **connection** stores named network and secret references. The PostgreSQL connection is also used by the **crawler**, which inspects only `sales.orders` and `sales.order_items` and writes metadata into the **Data Catalog** database. The Glue **job** reads those catalog tables and later writes through the separate named native MongoDB connection. That connection references `/aws-glue-postgres-mongodb-lab/mongodb-glue`, which contains connector credentials only; Glue cannot read the `/mongodb` bootstrap-administrator secret. Both connections use the same lab subnet and Glue security group; neither contains an inline username or password.

The repository deploys three fixed objects under the deterministic `glue/artifacts/` S3 prefix: the job entrypoint, `glue_lab.zip`, and `GIT_SHA`. This is intentionally not a release system. Repeating deployment overwrites those reviewed lab objects.

## How the Glue pieces fit together

These objects have different jobs; creating one does not automatically run another:

| Object | What it contains or does | What it does not do |
|---|---|---|
| PostgreSQL connection | A reusable name for the source network path and PostgreSQL secret reference | It does not copy rows or create catalog tables |
| MongoDB connection | A reusable name for the target network path and connector-only secret reference | It does not start MongoDB or run the migration |
| Crawler | Connects to PostgreSQL and inspects the two source table schemas | It records metadata only; it does not move business data |
| Data Catalog database/tables | Stores the discovered table names, columns, and Glue types | It is metadata, not another copy of PostgreSQL |
| Glue job | Reads the catalog tables, validates and transforms rows, then writes nested documents through the MongoDB connection | It runs only when the user explicitly starts it in runbook 04 |

The sequence in this runbook is therefore: upload reviewed code, inspect both connection definitions, run the crawler, and confirm the catalog. The migration job comes afterward.

## Step 1 — Select the personal lab identity

**Purpose**

Set the only user-supplied values and confirm the completed foundation/database steps.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Runbooks 01 and 02 were completed by the user.
- Terraform state is in `infrastructure/terraform/terraform.tfstate`.
- The PostgreSQL and MongoDB containers are healthy on EC2.
- AWS CLI v2, Terraform, GNU Make, Python 3, and `zip` are installed.

**Inputs**

`AWS_PROFILE` is the user's personal lab profile. `AWS_REGION` is fixed by the design.

**Command**

**User-run only.**

```bash
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="$AWS_REGION"
make doctor
```

**Expected result**

`make doctor` prints the resolved personal AWS account/principal, `us-east-1`, the relevant tool versions, the current Git revision, and finishes with `doctor: PASS`.

**Verify**

**User-run only.**

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query '{Account:Account,Arn:Arn}' --output table
```

Pass: the account and ARN belong to the intended personal account. Stop if the ARN is a work role or the Region printed by `make doctor` is not `us-east-1`. Keep the identifiers local; do not paste them into public evidence.

**Repeat, reset, or rollback**

Safe to repeat in each new shell. The identity calls are read-only and no AWS resource changes.

**If it fails**

- `The config profile ... could not be found`: run `aws configure list --profile "$AWS_PROFILE"`, return to runbook 00 to create or authenticate the profile, then repeat this step.
- Unexpected account or work-role ARN: stop, select the personal profile, and rerun `make doctor` before continuing.
- Wrong Region: re-export `AWS_REGION="us-east-1"` and `AWS_DEFAULT_REGION="$AWS_REGION"`, then repeat this step.

**Next**

Deploy the fixed-prefix artifacts.

## Step 2 — Deploy the Glue artifacts

**Purpose**

Package `src/glue_lab/` and upload the reusable code, thin job entrypoint, and current Git SHA to the existing encrypted S3 bucket.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Step 1 passes.
- The reviewed checkout is clean or its current SHA is the intended lab revision.
- Terraform output `artifact_bucket_name` is available.

**Inputs**

Uses `AWS_PROFILE` and `AWS_REGION` from Step 1. The prefix is fixed at `glue/artifacts/`.

**Command — User-run only**

```bash
APPROVE_GLUE_DEPLOY=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make deploy
```

**Expected result**

The command exits 0 and prints `deploy: PASS (prefix glue/artifacts; Git SHA recorded)`. It does not print a secret, connection URL, account ID, or bucket name.

**Verify — User-run only**

```bash
BUCKET="$(terraform -chdir=infrastructure/terraform output -raw artifact_bucket_name)"
for KEY in \
  glue/artifacts/jobs/postgres_orders_to_mongodb.py \
  glue/artifacts/python/glue_lab.zip \
  glue/artifacts/GIT_SHA
do
  aws s3api head-object --bucket "$BUCKET" --key "$KEY" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query '{Size:ContentLength,Encryption:ServerSideEncryption}' --output table
done
unset BUCKET KEY
```

Pass: all three calls exit 0, every size is greater than zero, and encryption is `AES256`. Do not paste account-specific output into a PR.

**Repeat, reset, or rollback**

Safe to rerun for the same reviewed checkout; the three fixed keys are overwritten. Terraform destroy removes the bucket. There is no artifact release/version history.

**If it fails**

- `NoSuchOutput`: complete `make infra-apply` using runbook 01, then repeat.
- `AccessDenied`: run `make doctor`, correct the personal profile, then repeat; do not broaden bucket policy from this runbook.
- `zip: command not found`: install the prerequisite identified by runbook 00, then repeat.

**Next**

Inspect the redacted connection topology.

## Step 3 — Inspect both connection definitions safely

**Purpose**

Confirm that Terraform created named JDBC and MongoDB connections in one subnet without displaying connection-property values.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 1 passes and Terraform apply completed.

**Inputs**

No new input.

**Command — User-run only**

```bash
POSTGRES_CONNECTION="$(terraform -chdir=infrastructure/terraform output -raw postgres_glue_connection_name)"
MONGODB_CONNECTION="$(terraform -chdir=infrastructure/terraform output -raw mongodb_glue_connection_name)"
for CONNECTION in "$POSTGRES_CONNECTION" "$MONGODB_CONNECTION"
do
  aws glue get-connection --name "$CONNECTION" --hide-password \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query 'Connection.{Name:Name,Type:ConnectionType,Subnet:PhysicalConnectionRequirements.SubnetId,SecurityGroups:PhysicalConnectionRequirements.SecurityGroupIdList,PropertyKeys:keys(ConnectionProperties)}' \
    --output table
done
```

**Expected result**

One row reports type `JDBC`, one reports `MONGODB`, both show the same subnet/security group, and only property key names—not values—are shown. Each includes `SECRET_ID`; neither includes `USERNAME` or `PASSWORD`.

**Verify — User-run only**

```bash
(
set -euo pipefail
umask 077
connection_tmp_dir="$(mktemp -d /tmp/glue-connections.XXXXXX)"
cleanup_connection_files() {
  rm -rf "$connection_tmp_dir"
}
trap cleanup_connection_files EXIT
aws glue get-connection --name "$POSTGRES_CONNECTION" --hide-password \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --output json \
  >"$connection_tmp_dir/postgres.json"
aws glue get-connection --name "$MONGODB_CONNECTION" --hide-password \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --output json \
  >"$connection_tmp_dir/mongodb.json"
python3 - "$connection_tmp_dir/postgres.json" "$connection_tmp_dir/mongodb.json" <<'PY'
import json
import sys
from pathlib import Path


def read_connection(path: str) -> dict:
    return json.loads(Path(path).read_text())["Connection"]


postgres = read_connection(sys.argv[1])
mongodb = read_connection(sys.argv[2])
for connection, expected_type in ((postgres, "JDBC"), (mongodb, "MONGODB")):
    if connection.get("ConnectionType") != expected_type:
        raise SystemExit(f"ERROR: expected {expected_type} connection type")
    property_keys = set(connection.get("ConnectionProperties", {}))
    if "SECRET_ID" not in property_keys or property_keys & {"USERNAME", "PASSWORD"}:
        raise SystemExit("ERROR: connection credential-reference contract failed")

postgres_network = postgres["PhysicalConnectionRequirements"]
mongodb_network = mongodb["PhysicalConnectionRequirements"]
if not postgres_network.get("SubnetId") or (
    postgres_network.get("SubnetId") != mongodb_network.get("SubnetId")
):
    raise SystemExit("ERROR: Glue connections do not share one nonempty subnet")
postgres_groups = set(postgres_network.get("SecurityGroupIdList", []))
mongodb_groups = set(mongodb_network.get("SecurityGroupIdList", []))
if not postgres_groups or postgres_groups != mongodb_groups:
    raise SystemExit("ERROR: Glue connections do not share the Glue security group")
print("connection definitions: PASS")
PY
)
```

Pass: `connection definitions: PASS` prints. The temporary JSON files are mode-restricted, are deleted by the EXIT trap, and are never committed or copied into public evidence.

**Repeat, reset, or rollback**

Read-only and safe to repeat. Terraform owns corrections; do not edit a connection in the console.

**If it fails**

- Missing connection output: run `terraform -chdir=infrastructure/terraform output`, confirm this lab's state is selected, and repeat Step 3.
- Connection type, subnet, security-group, or credential-reference error: preserve only the redacted error line, stop, and file a separate issue/PR. Do not patch the live connection manually.
- `AccessDenied`: rerun `make doctor`, correct the personal profile, and repeat Step 3; do not broaden permissions from the console.

**Next**

Run the crawler, which exercises the PostgreSQL connection path.

## Step 4 — Run the unscheduled crawler and assert the catalog

**Purpose**

Start the one crawler, wait at most ten minutes, require a successful terminal state, and assert exact table names, column order, and inferred Glue types.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Steps 1–3 pass.
- PostgreSQL is healthy and its secret value matches the initialized container.
- Database host security group permits TCP 5432 only from the Glue security group.

**Inputs**

`CRAWLER_TIMEOUT_SECONDS` is optional, defaults to `600`, and cannot exceed `1200`; `CRAWLER_POLL_SECONDS` defaults to `10` and cannot exceed `60`.

**Command — User-run only**

```bash
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
APPROVE_GLUE_CRAWL=1 CRAWLER_TIMEOUT_SECONDS=600 CRAWLER_POLL_SECONDS=10 make crawl
```

**Expected result**

Before start, the bounded waiter records the prior `LastCrawl.StartTime`. A failed `start-crawler` is fatal and never adopts another run. Success requires a strictly newer start-time witness and a successful terminal result, then prints `crawl: PASS (exact tables, columns, and types verified; output redacted)`. The script expects only `orders` and `order_items`, with the ordered names and Glue types derived from the schemas in `DESIGN.md`. It prints no records or connection-property values.

**Verify — User-run only**

```bash
CRAWLER="$(terraform -chdir=infrastructure/terraform output -raw glue_crawler_name)"
aws glue get-crawler --name "$CRAWLER" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'Crawler.{State:State,LastStatus:LastCrawl.Status,Schedule:Schedule}' --output table
unset CRAWLER
```

Pass: state is `READY`, last status is `SUCCEEDED`, and schedule is empty. `make crawl` already fails unless the exact catalog assertion passes.

**Repeat, reset, or rollback**

Safe to rerun. `CRAWL_EVERYTHING` updates the same two catalog tables; it does not create duplicate table names or a schedule. Terraform destroy removes the crawler/database.

**If it fails**

- Timeout or `FAILED`: resolve the crawler name again because the verification block unsets its temporary variable, then inspect only the bounded status/error summary:

  ```bash
  CRAWLER="$(terraform -chdir=infrastructure/terraform output -raw glue_crawler_name)"
  aws glue get-crawler --name "$CRAWLER" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query 'Crawler.{State:State,LastStatus:LastCrawl.Status,LastError:LastCrawl.ErrorMessage}' \
    --output table
  unset CRAWLER
  ```

  Correct the reported connection, authentication, or schema condition, then repeat `make crawl` with the same bounded timeout inputs.
- JDBC connection error: rerun `make ec2-bootstrap`, confirm TCP 5432 is sourced only from the Glue security group in Terraform, and repeat `make crawl`.
- Secret authentication error after rotation: follow runbook 02 and run `make ec2-reset-data`, then repeat.
- Catalog mismatch: do not delete unrelated tables broadly. Confirm this Terraform state owns the catalog database; then file a separate issue/PR with redacted names/schema differences.
- Never add public database ingress, SSH, or a NAT Gateway.

**Next**

Continue to [04 — Run the snapshot migration](04-RUN-MIGRATION.md).
