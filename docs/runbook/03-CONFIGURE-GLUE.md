# 03 — Configure and Verify AWS Glue

Owner: `GLUE-030`  
Status: implementation complete

> **User-run only:** Every AWS command in this runbook is run by the user after cloning completed reviewed code. Agents must never request or use AWS credentials. No agent-run live AWS evidence is required; development acceptance uses static/mock/Terraform/unit/container checks. A failure in this user-run lab becomes a separate issue/PR.

A Glue **connection** stores named network and secret references. The PostgreSQL connection is also used by the **crawler**, which inspects only `sales.orders` and `sales.order_items` and writes metadata into the **Data Catalog** database. The Glue **job** reads those catalog tables and later writes through the separate named native MongoDB connection. That connection references `/aws-glue-postgres-mongodb-lab/mongodb-glue`, which contains connector credentials only; Glue cannot read the `/mongodb` bootstrap-administrator secret. Both connections use the same lab subnet and Glue security group; neither contains an inline username or password.

The repository deploys three fixed objects under the deterministic `glue/artifacts/` S3 prefix: the job entrypoint, `glue_lab.zip`, and `GIT_SHA`. This is intentionally not a release system. Repeating deployment overwrites those reviewed lab objects.

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

```bash
export AWS_PROFILE="personal-lab"
export AWS_REGION="us-east-1"
```

**Expected result**

Both variables are set without output.

**Verify**

```bash
test -n "$AWS_PROFILE" && test "$AWS_REGION" = "us-east-1" && printf '%s\n' 'Glue inputs: PASS'
```

Pass: `Glue inputs: PASS` prints. Identity verification itself remains the user-run `make doctor` step from runbook 01.

**Repeat, reset, or rollback**

Safe to repeat in each new shell. No AWS resource changes.

**If it fails**

If the pass line does not print, correct the two exports and repeat. Stop rather than selecting work credentials.

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
PG_SUBNET="$(aws glue get-connection --name "$POSTGRES_CONNECTION" --hide-password --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Connection.PhysicalConnectionRequirements.SubnetId' --output text)"
MONGO_SUBNET="$(aws glue get-connection --name "$MONGODB_CONNECTION" --hide-password --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Connection.PhysicalConnectionRequirements.SubnetId' --output text)"
test -n "$PG_SUBNET" && test "$PG_SUBNET" = "$MONGO_SUBNET" && printf '%s\n' 'connection topology: PASS'
unset PG_SUBNET MONGO_SUBNET
```

Pass: `connection topology: PASS` prints.

**Repeat, reset, or rollback**

Read-only and safe to repeat. Terraform owns corrections; do not edit a connection in the console.

**If it fails**

If names are missing, run `terraform -chdir=infrastructure/terraform output` and confirm the current state. If subnets differ or inline credential keys appear, stop and file a separate issue/PR; do not patch the live connection manually.

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

- Timeout or `FAILED`: inspect the crawler's last error with `aws glue get-crawler --name "$CRAWLER"` while keeping secret values out of evidence.
- JDBC connection error: rerun `make ec2-bootstrap`, confirm TCP 5432 is sourced only from the Glue security group in Terraform, and repeat `make crawl`.
- Secret authentication error after rotation: follow runbook 02 and run `make ec2-reset-data`, then repeat.
- Catalog mismatch: do not delete unrelated tables broadly. Confirm this Terraform state owns the catalog database; then file a separate issue/PR with redacted names/schema differences.
- Never add public database ingress, SSH, or a NAT Gateway.

**Next**

Continue to [04 — Run the snapshot migration](04-RUN-MIGRATION.md).
