# 07 — Troubleshooting and Optional EC2 Write Path

Owner: `GLUE-060` final review
Status: implementation complete

> **User-run only:** AWS, SSM, Glue, database, and GitHub operations below are performed only by the user from a completed reviewed clone. Agents never request or use AWS credentials. Keep diagnostics local and redact account IDs, ARNs, resource IDs, bucket names, endpoints, addresses, full records, and secret values.

Preserve the version-1 design while diagnosing. Never add a NAT Gateway, public database ingress, SSH bastion, alternate ETL engine/connector, destructive preload, CDC, or broad cleanup.

## Step 1 — Run bounded first-line diagnostics

**Purpose**

Confirm the current step's exact prerequisites before changing data or infrastructure.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

The original clean checkout and local Terraform state remain available. The user knows which numbered runbook step failed.

**Inputs**

```bash
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
```

Unset ambient credentials, every `AWS_ENDPOINT_URL*`, and Terraform overrides as shown in runbooks 05–06.

**Command — User-run only**

```bash
make doctor
test "$(terraform -chdir=infrastructure/terraform workspace show)" = default
git status --short
```

**Expected result**

`doctor: PASS`, default workspace, and an empty Git status. If one fails, diagnose it before retrying the operational target.

**Verify — User-run only**

```bash
test "$(terraform -chdir=infrastructure/terraform output -raw aws_region)" = us-east-1
printf '%s\n' 'first-line diagnostics: PASS'
```

Pass: the message prints without exposing identity or endpoint values.

**Repeat, reset, or rollback**

Read-only and safe to repeat. Do not reset data/state merely to make diagnostics pass.

**If it fails**

Use the matching failure entry below. Correct the smallest prerequisite, then repeat the exact failed runbook command.

**Next**

Return to the numbered runbook step that failed. The optional GitHub workflow at the end is unrelated to core-lab recovery.

## Focused failure entries

### Wrong AWS profile, account, Region, or endpoint override

- **Step:** any user-run AWS step.
- **Likely cause:** work credentials/profile selected, Region differs from `us-east-1`, or an `AWS_ENDPOINT_URL*`/Terraform override exists.
- **Diagnose — User-run only:** `aws configure list --profile "$AWS_PROFILE"; env | grep -E '^(AWS_ENDPOINT_URL|TF_(WORKSPACE|DATA_DIR|CLI_ARGS))' || true`
- **Expected diagnostic result:** personal profile/`us-east-1`; the override search is empty.
- **Fix:** select the personal profile, export `AWS_REGION=us-east-1`, and unset only the listed override variables.
- **Retry:** repeat `make doctor`, then the failed target with its explicit approval.
- **Reset impact:** none.

### Missing AWS permission or `iam:PassRole`

- **Step:** infrastructure apply, Glue configuration/run, inventory, or destroy verification.
- **Likely cause:** the personal lab principal lacks the exact action named by `AccessDenied`.
- **Diagnose — User-run only:** `aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION"`
- **Expected diagnostic result:** intended personal identity; the original error names the denied action/resource.
- **Fix:** add only that lab-scoped permission; `iam:PassRole` must be limited to the lab EC2/Glue roles and intended service.
- **Retry:** repeat the exact failed runbook command.
- **Reset impact:** none unless a reviewed Terraform apply partially succeeded; inspect state first.

### Terraform provider/init or state identity failure

- **Step:** runbooks 01 or 06.
- **Likely cause:** provider cache missing, wrong workspace/state, or ambient CLI overrides.
- **Diagnose:** `terraform -chdir=infrastructure/terraform version; terraform -chdir=infrastructure/terraform workspace show; git status --short`
- **Expected diagnostic result:** pinned-compatible Terraform, workspace `default`, clean tree.
- **Fix:** unset Terraform overrides and run `make infra-init`; never create another workspace or remote backend.
- **Retry:** rerun the failed plan command and review the new saved plan.
- **Reset impact:** provider initialization only; no AWS mutation.

### EC2 SSM status is not online

- **Step:** database bootstrap, validation, or rerun proof.
- **Likely cause:** bootstrap still running, instance stopped, SSM agent/profile path unavailable.
- **Diagnose — User-run only:** `INSTANCE_ID="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"; aws ssm describe-instance-information --profile "$AWS_PROFILE" --region "$AWS_REGION" --filters "Key=InstanceIds,Values=$INSTANCE_ID" --query 'InstanceInformationList[0].PingStatus' --output text; unset INSTANCE_ID`
- **Expected diagnostic result:** `Online`.
- **Fix:** inspect EC2 state and user-data/SSM logs through the AWS console; correct the reviewed Terraform/bootstrap issue. Do not open SSH.
- **Retry:** repeat `make ec2-bootstrap` or the failed validation target.
- **Reset impact:** none unless explicitly using `make ec2-reset-data`.

### Git clone or pull fails on EC2

- **Step:** EC2 bootstrap.
- **Likely cause:** public GitHub egress/DNS problem, local EC2 checkout changes, or non-fast-forward branch.
- **Diagnose — User-run only:** in an SSM session run `sudo -u ec2-user git -C /opt/aws-glue-postgres-mongodb-lab status --short --branch`.
- **Expected diagnostic result:** clean reviewed branch with no local commit divergence.
- **Fix:** preserve unexpected work before any change. For a clean stale clone, rerun the bootstrap pull. Do not force-push or rewrite history.
- **Retry:** `make ec2-bootstrap` from the Mac.
- **Reset impact:** repository checkout only.

### Docker image pull or container health failure

- **Step:** runbook 02.
- **Likely cause:** image egress, invalid secret-seeded environment, or persistent-volume credential mismatch.
- **Diagnose — User-run only:** in SSM run `cd /opt/aws-glue-postgres-mongodb-lab && sudo -u ec2-user docker compose --env-file .env -f docker/compose.yaml ps` only while bootstrap's private `.env` exists; otherwise rerun the guarded bootstrap instead of recreating it manually.
- **Expected diagnostic result:** exactly `postgres` and `mongodb`, both healthy.
- **Fix:** after intentional secret rotation use `make ec2-reset-data`; plain bootstrap cannot update initialized volume credentials.
- **Retry:** `make ec2-bootstrap` or `make ec2-reset-data` as documented.
- **Reset impact:** `ec2-reset-data` removes only the two fixed Compose volumes and reseeds synthetic data.

### PostgreSQL authentication or JDBC failure

- **Step:** crawler, Glue job, reconciliation.
- **Likely cause:** secret/container volume mismatch, unhealthy source, or Glue security-group path.
- **Diagnose — User-run only:** run the runbook 02 source assertion through the implemented bootstrap, then `aws glue get-connection --name aws-glue-postgres-mongodb-lab-postgres --hide-password --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Connection.ConnectionType' --output text`.
- **Expected diagnostic result:** source assertions pass and type is `JDBC`.
- **Fix:** correct secret rotation through exact reset or restore the reviewed security-group reference; never expose port 5432 publicly.
- **Retry:** repeat `make crawl`, `make run`, or approved `make validate`.
- **Reset impact:** only an explicit exact data reset changes source volumes.

### MongoDB authentication or connection failure

- **Step:** Glue write, reconciliation, or rerun proof.
- **Likely cause:** connector secret differs from initialized user, target unhealthy, or port-27017 security path broken.
- **Diagnose — User-run only:** `aws glue get-connection --name aws-glue-postgres-mongodb-lab-mongodb --hide-password --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Connection.ConnectionType' --output text`.
- **Expected diagnostic result:** `MONGODB`; runbook 02 container checks pass.
- **Fix:** use exact secret-rotation reset or restore reviewed security-group references; never use root credentials for Glue or public ingress.
- **Retry:** repeat the failed job/validation target.
- **Reset impact:** only exact reset removes target volume.

### Glue ENI or security-group failure

- **Step:** crawler/job start.
- **Likely cause:** Glue self-reference, subnet, endpoint route, or EC2 database-host rule differs from Terraform.
- **Diagnose — User-run only:** `aws glue get-job --job-name aws-glue-postgres-mongodb-lab-orders-to-mongodb --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Job.Connections.Connections' --output json`.
- **Expected diagnostic result:** exactly the two lab connection names; Terraform static/mock checks remain green.
- **Fix:** return configuration to reviewed Terraform; do not add NAT/public ingress.
- **Retry:** create/review/apply a normal Terraform plan, then repeat the crawler/job.
- **Reset impact:** infrastructure configuration only.

### Secrets Manager access failure

- **Step:** bootstrap, Glue connector, reconciliation, rerun proof.
- **Likely cause:** missing value, wrong exact secret name, or IAM policy mismatch.
- **Diagnose — User-run only:** `for name in postgres mongodb mongodb-glue; do aws secretsmanager describe-secret --secret-id "/aws-glue-postgres-mongodb-lab/$name" --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Name --output text >/dev/null || exit; done`
- **Expected diagnostic result:** all three calls exit `0` without reading or printing values.
- **Fix:** use approved `make secrets-put`; after rotation use `make ec2-reset-data`.
- **Retry:** repeat bootstrap or the failed target.
- **Reset impact:** secret value update; exact reset required for existing database volumes.

### Crawler failure or wrong catalog tables

- **Step:** runbook 03.
- **Likely cause:** JDBC path/auth failure or stale/unexpected table schema.
- **Diagnose — User-run only:** `aws glue get-crawler --name aws-glue-postgres-mongodb-lab-orders --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'Crawler.{State:State,Status:LastCrawl.Status,Error:LastCrawl.ErrorMessage}' --output json`.
- **Expected diagnostic result:** state `READY`, status `SUCCEEDED`, no error; guarded crawler assertion sees only `orders` and `order_items`.
- **Fix:** correct source/connectivity, then rerun the unscheduled crawler. Do not create another crawler.
- **Retry:** `APPROVE_GLUE_CRAWL=1 make crawl`.
- **Reset impact:** Data Catalog metadata only.

### Glue job failure or timeout

- **Step:** runbook 04 or rerun proof.
- **Likely cause:** source validation, connector, or bounded waiter failure.
- **Diagnose — User-run only:** `aws logs tail /aws-glue/jobs/error --since 1h --profile "$AWS_PROFILE" --region "$AWS_REGION"`.
- **Expected diagnostic result:** bounded phase/error without credentials/full records; redact before sharing.
- **Fix:** correct the specific source/connectivity issue. Do not increase architecture scope or bypass validation.
- **Retry:** `APPROVE_GLUE_RUN=1 make run`.
- **Reset impact:** deterministic upsert of emitted `_id` documents only.

### MongoDB duplicate or replacement behavior mismatch

- **Step:** runbook 05 rerun proof.
- **Likely cause:** deterministic `_id`/`replaceDocument=true` behavior differs from expected connector output.
- **Diagnose — User-run only:** rerun `APPROVE_GLUE_VALIDATE=1 make validate` and retain only category/count JSON plus rerun count/hash.
- **Expected diagnostic result:** unchanged second run has identical counts/hash and no duplicate key; controlled replacement changes hash then reconciles.
- **Fix:** stop and file a separate issue/PR with redacted evidence. Do not switch connectors or clear the collection.
- **Retry:** only after reviewed correction, rerun `APPROVE_GLUE_RERUN=1 make rerun-test`.
- **Reset impact:** fixed synthetic fixtures only.

### Reconciliation count, total, ordering, normalization, deletion, or stale mismatch

- **Step:** runbook 05 Step 2/3.
- **Likely cause:** incomplete/failed Glue run, changed fixture, wrong target content, or the documented soft-delete limitation.
- **Diagnose — User-run only:** inspect only `/var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json` through SSM using runbook 05; do not print source/target projections.
- **Expected diagnostic result:** one or more bounded mismatch categories and no keys/records.
- **Fix:** for ordinary mismatch, correct the failed phase and rerun Glue. For the controlled stale case, delete exactly target `_id=1003` through the implemented rerun action; never broaden scope.
- **Retry:** `APPROVE_GLUE_RERUN=1 make rerun-test` or approved `make validate`.
- **Reset impact:** fixed synthetic rows/document only during rerun proof.

### Terraform destroy blocked by S3 objects or dependencies

- **Step:** runbook 06 Step 4.
- **Likely cause:** Terraform reported a specific residual object/dependency or partial apply.
- **Diagnose:** `terraform -chdir=infrastructure/terraform state list` plus the exact Terraform error; do not print state content.
- **Expected diagnostic result:** only known residual addresses or empty state with a known-service category count.
- **Fix:** if state remains, create and review a fresh smaller destroy plan. If state is empty, rerun only `scripts/verify-destroyed.sh` with the shell-memory account/bucket bindings. A real out-of-state remainder needs separately reviewed exact handling.
- **Retry:** new `make destroy-plan`/approved `make destroy-lab`, or the standalone read-only verifier.
- **Reset impact:** destruction only for exact reviewed state; no broad service cleanup.

## Optional — GitHub-to-EC2 write workflow

This workflow is **not required for the core lab**. The normal path is Mac feature branch → GitHub PR → reviewed `main` → EC2 public clone/pull. Use the following only to experiment with pushing a non-`main` feature branch from the disposable EC2 host.

### Step 2 — Generate and display only the EC2 public key

**Purpose**

Create a repository-specific Ed25519 deploy-key pair on EC2 while keeping the private key on that disposable host.

**Run from**

`EC2 through Systems Manager Session Manager`

**Prerequisites**

Runbook 02 completed, the session runs as `ec2-user`, and the repository exists at `/opt/aws-glue-postgres-mongodb-lab`.

**Inputs**

None; the script uses the fixed repository/key directory.

**Command — User-run only**

```bash
/opt/aws-glue-postgres-mongodb-lab/scripts/configure-ec2-github-write.sh
```

**Expected result**

Only the public key is printed. The private key remains mode `0600` under `~/.ssh/aws-glue-postgres-mongodb-lab/` and is not printed.

**Verify**

```bash
test "$(stat -c '%a' "$HOME/.ssh/aws-glue-postgres-mongodb-lab/id_ed25519")" = 600
```

Pass: the test exits `0`; do not display the private file.

**Repeat, reset, or rollback**

Safe to repeat; the existing key pair is reused. Remove the exact key directory only after retiring its GitHub registration.

**If it fails**

Confirm the user is `ec2-user` and `ssh-keygen` exists. Do not generate a key on the Mac and copy its private half to EC2.

**Next**

Add only the printed public key in GitHub.

### Step 3 — Register the public key for this repository

**Purpose**

Authorize only this repository for optional EC2 writes.

**Run from**

`GitHub web UI — Korrojo/aws-glue-postgres-mongodb-lab > Settings > Deploy keys`

**Prerequisites**

Step 2 printed the public key and the user has repository administration permission.

**Inputs**

Title `aws-glue-postgres-mongodb-lab-ec2-deploy-key`; key is the exact public line from Step 2; check **Allow write access**.

**Command — User-run only**

Click **Add deploy key** with those exact inputs.

**Expected result**

One enabled write deploy key appears for this repository. No GitHub token or private key is placed on EC2/Terraform.

**Verify — User-run only**

Confirm the key fingerprint in GitHub matches `ssh-keygen -lf "$HOME/.ssh/aws-glue-postgres-mongodb-lab/id_ed25519.pub"` from EC2.

Pass: fingerprints match and only the public key crossed the session boundary.

**Repeat, reset, or rollback**

Do not add duplicates. Roll back by deleting only this deploy key in GitHub settings.

**If it fails**

Confirm repository admin rights and public-key format. Never paste the private-key file.

**Next**

Configure verified GitHub SSH host keys and push only a feature branch.

### Step 4 — Configure SSH and push a non-main feature branch

**Purpose**

Pin GitHub's published SSH host keys, use only the deploy-key identity, and prevent direct `main` push by requiring an explicit feature branch.

**Run from**

`EC2 through Systems Manager Session Manager`

**Prerequisites**

Step 3 completed and the EC2 checkout is clean.

**Inputs**

```bash
export FEATURE_BRANCH="feature/ec2-lab-notes"
test "$FEATURE_BRANCH" != main
```

Choose a new non-`main` branch name.

**Command — User-run only**

```bash
CONFIGURE_REMOTE=1 /opt/aws-glue-postgres-mongodb-lab/scripts/configure-ec2-github-write.sh
cd /opt/aws-glue-postgres-mongodb-lab
git switch -c "$FEATURE_BRANCH"
git push --set-upstream origin "$FEATURE_BRANCH"
```

**Expected result**

The script obtains GitHub host keys from `https://api.github.com/meta`, configures strict host verification and the exact private key, changes only this checkout's origin to SSH, and pushes the feature branch. It does not push `main`.

**Verify — User-run only**

```bash
git remote get-url origin
git branch --show-current
git ls-remote --exit-code --heads origin "$FEATURE_BRANCH" >/dev/null
```

Pass: origin is `git@github.com:Korrojo/aws-glue-postgres-mongodb-lab.git`, current branch equals the feature branch, and the remote head exists.

**Repeat, reset, or rollback**

Subsequent feature-branch pushes reuse the key. At teardown, remove only this deploy key in GitHub using runbook 06 Step 5; EC2 destruction removes the private key.

**If it fails**

- Host-key failure: rerun the configuration script; do not disable `StrictHostKeyChecking`.
- Permission denied: confirm the exact public key is write-enabled for this repository.
- Rejected branch: fetch/review divergence; never force-push `main`.

**Next**

Open a normal GitHub PR for the feature branch. This optional path does not alter the core lab sequence.
