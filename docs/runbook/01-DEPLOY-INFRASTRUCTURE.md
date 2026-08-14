# 01 — Deploy AWS Infrastructure

Owner: `GLUE-020`  
Status: implemented by `GLUE-020`

Create the disposable AWS foundation from one understandable Terraform root. This runbook creates no Glue job, crawler, connection, NAT Gateway, load balancer, remote state, deployment pipeline, database credential value, or inbound SSH rule.

> [!CAUTION]
> `make infra-apply` creates billable resources in the currently selected AWS account. Confirm a personal identity and `us-east-1` immediately before planning and applying. Never paste account IDs, ARNs containing an account ID, secret values, public IP addresses, or live endpoints into commits or PR evidence.

## Step 1 — Pin the repository revision and AWS session

**Purpose**

Prove which reviewed code and personal AWS identity will create the lab.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- [00 — Prerequisites](00-PREREQUISITES.md) completed.
- `git status --short` is empty.
- The selected profile belongs to the intended personal account.

**Inputs**

- `AWS_PROFILE`: personal profile name.
- `AWS_REGION`: exactly `us-east-1`.
- `TF_VAR_repository_ref`: normally `main`. A PR reviewer may set the current public feature branch to test that exact branch before merge.

**Command**

```bash
export AWS_PROFILE=personal-glue-lab
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export TF_VAR_repository_ref="$(git branch --show-current)"

git status --short
git rev-parse HEAD
make doctor
```

For a normal merged lab run, require `main`:

```bash
test "$(git branch --show-current)" = main
export TF_VAR_repository_ref=main
```

**Expected result**

The tree is clean, a Git SHA is printed, and `make doctor` ends with `doctor: PASS` after showing the expected personal principal and Region.

**Verify**

```bash
test "$AWS_REGION" = us-east-1
aws sts get-caller-identity --profile "$AWS_PROFILE" --query Arn --output text
```

Read the result locally and stop if it is not the intended personal principal. Do not save it in the repository.

**Repeat, reset, or rollback**

Repeat whenever the Git branch, AWS profile, or Region changes. Unset `TF_VAR_repository_ref` to return to Terraform's `main` default.

**If it fails**

Return to runbook 00. Missing AWS authentication or an unexpected account is a hard stop; static tests are not a substitute for a confirmed deployment identity.

**Next**

Review exactly what Terraform is allowed to create.

## Step 2 — Review the bounded resource model

**Purpose**

Understand the plan before Terraform contacts AWS.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

Step 1 passed.

**Inputs**

No additional input.

**Command**

```bash
find infrastructure/terraform -maxdepth 2 -type f -print
make terraform-check
```

**Expected result**

Terraform formatting, initialization, validation, and the credential-free mocked plan test pass. The root contains:

- one VPC, one public subnet in one Availability Zone, one internet gateway, one route table;
- an S3 gateway endpoint and a Secrets Manager interface endpoint;
- Glue, database-host, and endpoint security groups;
- one private encrypted S3 artifact bucket with a one-day `tmp/` lifecycle rule;
- two empty Secrets Manager secret containers;
- one EC2 role/profile and one Glue role;
- one Amazon Linux 2023 `t3.medium` instance with an encrypted 30 GiB gp3 root volume;
- user data that installs Docker/Git, verifies pinned Docker Compose `v5.4.0`, clones the selected public branch, enables SSM, and records the Git SHA.

There is no NAT Gateway, EIP, load balancer, SSH key pair, remote state, module tree, or secret value in Terraform.

**Verify**

```bash
terraform -chdir=infrastructure/terraform test
```

The result is `Success! 1 passed, 0 failed.`

**Repeat, reset, or rollback**

Credential-free and safe to repeat. `.terraform/` is ignored; delete only that project directory if provider initialization must be repeated from scratch.

**If it fails**

- Run `terraform -chdir=infrastructure/terraform fmt -recursive` and inspect any source change before committing it.
- Confirm Terraform can reach the provider registry.
- Do not remove the provider lock file to bypass a checksum or version failure.

**Next**

Initialize live local state.

## Step 3 — Initialize Terraform

**Purpose**

Install the locked providers and prepare local state without adding a remote backend.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

Steps 1–2 passed.

**Inputs**

The exported AWS profile, Region, and repository ref.

**Command**

```bash
make infra-init
```

**Expected result**

Terraform reports successful initialization using the versions recorded in `.terraform.lock.hcl`. State remains local under `infrastructure/terraform/` and is ignored by Git.

**Verify**

```bash
terraform -chdir=infrastructure/terraform providers

git status --short
```

Only intentional source/documentation changes may appear; `.terraform/` and state files must not appear.

**Repeat, reset, or rollback**

Safe to repeat. Do not add Terraform Cloud, S3 state, DynamoDB locking, or environment workspaces for this single-user lab.

**If it fails**

Check network access and the checksums in `.terraform.lock.hcl`. Never commit `.terraform/` or a provider binary.

**Next**

Create and inspect a saved plan.

## Step 4 — Create and review the infrastructure plan

**Purpose**

Review intended mutations before creating any AWS resource.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- Terraform initialized.
- Personal AWS session active.
- No existing plan is being reviewed under another Git SHA.

**Inputs**

`AWS_PROFILE`, `AWS_REGION=us-east-1`, and `TF_VAR_repository_ref`.

**Command**

```bash
make infra-plan
terraform -chdir=infrastructure/terraform show tfplan
```

**Expected result**

The saved plan contains only project-tagged resources described in Step 2. It resolves an Amazon Linux 2023 AMI from the public SSM parameter. It contains no database password, MongoDB password, private deploy key, public inbound database rule, SSH rule, NAT Gateway, EIP, Glue job, or scheduled resource. `make infra-plan` also writes ignored mode-`0600` metadata binding the plan hash to the current AWS account, profile, Region, and Git SHA.

**Verify**

Inspect the plan and answer all of these before applying:

```text
[ ] Account and Region are personal and us-east-1.
[ ] Exactly one VPC, subnet, internet gateway, route table, and EC2 instance are planned.
[ ] S3 and Secrets Manager are the only VPC endpoint services.
[ ] Database ingress references the Glue security group on 5432 and 27017.
[ ] No ingress rule opens 22, 5432, or 27017 to a CIDR.
[ ] No NAT Gateway, EIP, load balancer, remote backend, or Glue workload is planned.
[ ] Secret resources have names/descriptions only; no secret version or value is planned.
[ ] Default tags include Project, Environment=lab, and ManagedBy=terraform.
```

A machine-readable local copy may be inspected without committing it:

```bash
terraform -chdir=infrastructure/terraform show -json tfplan > /tmp/aws-glue-lab-plan.json
```

**Repeat, reset, or rollback**

Re-running `make infra-plan` replaces the ignored `tfplan` and `.tfplan.identity.json` together. Delete `/tmp/aws-glue-lab-plan.json` after review. If code, profile, Region, Git ref, plan bytes, or account changes, discard both artifacts and create a new plan.

**If it fails**

- `No valid credential sources`: refresh the personal profile.
- `AccessDenied`: add only the missing lab-scoped permission; do not switch to an employer account.
- `InvalidAMIID` or SSM parameter error: verify `us-east-1` and provider access.
- Quota errors: remove stale personal lab resources or request a small personal-account quota adjustment.

**Next**

Apply only the reviewed saved plan.

## Step 5 — Apply the reviewed plan

**Purpose**

Create exactly the plan reviewed in Step 4.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

Every Step 4 checkbox is satisfied and `tfplan` was generated under the current Git SHA and personal AWS session.

**Inputs**

An explicit one-command gate: `APPROVE_LAB_APPLY=1`.

**Command**

```bash
APPROVE_LAB_APPLY=1 make infra-apply
```

**Expected result**

Before Terraform can mutate AWS, the apply script re-resolves STS and verifies the account, profile name, Region, Git SHA, and SHA-256 plan hash against the private metadata saved in Step 4. A mismatch fails closed. On success Terraform applies the saved plan and prints nonsensitive outputs; do not copy live identifiers into tracked files or public PR evidence.

**Verify**

```bash
terraform -chdir=infrastructure/terraform output
terraform -chdir=infrastructure/terraform plan -detailed-exitcode
```

The second command exits `0` with no changes. Exit `2` means drift or a changed input; inspect it before continuing.

**Repeat, reset, or rollback**

`infra-apply` consumes only the identity-bound saved plan and refuses to run without the explicit gate, profile, Region, clean matching Git SHA, matching STS account, and unchanged plan hash. Re-plan before a later apply. Do not run `terraform destroy` here; final destruction belongs to [06 — Destroy](06-DESTROY.md).

**If it fails**

Do not blindly re-apply. Read the failing resource, run `terraform plan`, and confirm whether Terraform recorded partial state. Resolve only that scoped issue.

**Next**

Verify the deployed foundation and SSM.

## Step 6 — Verify VPC, endpoints, S3, secrets, IAM, EC2, and SSM

**Purpose**

Prove that the foundation exists, is tagged, and exposes no inbound SSH/database path.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

Step 5 completed.

**Inputs**

Terraform outputs resolved locally.

**Command**

```bash
instance_id="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"
vpc_id="$(terraform -chdir=infrastructure/terraform output -raw vpc_id)"
subnet_id="$(terraform -chdir=infrastructure/terraform output -raw subnet_id)"
database_sg="$(terraform -chdir=infrastructure/terraform output -raw database_host_security_group_id)"
glue_sg="$(terraform -chdir=infrastructure/terraform output -raw glue_security_group_id)"
bucket="$(terraform -chdir=infrastructure/terraform output -raw artifact_bucket_name)"

aws ec2 describe-vpcs --profile "$AWS_PROFILE" --region "$AWS_REGION" --vpc-ids "$vpc_id"
aws ec2 describe-subnets --profile "$AWS_PROFILE" --region "$AWS_REGION" --subnet-ids "$subnet_id"
aws ec2 describe-vpc-endpoints --profile "$AWS_PROFILE" --region "$AWS_REGION" --filters "Name=vpc-id,Values=$vpc_id"
aws ec2 describe-security-group-rules --profile "$AWS_PROFILE" --region "$AWS_REGION" --filters "Name=group-id,Values=$database_sg,$glue_sg"
aws s3api get-public-access-block --profile "$AWS_PROFILE" --region "$AWS_REGION" --bucket "$bucket"
aws secretsmanager describe-secret --profile "$AWS_PROFILE" --region "$AWS_REGION" --secret-id /aws-glue-postgres-mongodb-lab/postgres
aws secretsmanager describe-secret --profile "$AWS_PROFILE" --region "$AWS_REGION" --secret-id /aws-glue-postgres-mongodb-lab/mongodb
aws ssm describe-instance-information --profile "$AWS_PROFILE" --region "$AWS_REGION" --filters "Key=InstanceIds,Values=$instance_id"
```

**Expected result**

- One lab VPC/subnet and exactly two VPC endpoints are returned.
- Database ingress is only from the Glue security-group ID on TCP 5432 and 27017.
- Glue has its self-referencing all-TCP rule.
- S3 public access flags are all `true`.
- Both secret containers exist, but no value has been created yet.
- SSM reports the instance `Online`; no SSH session or port 22 is required.

**Verify**

```bash
aws ssm describe-instance-information --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --filters "Key=InstanceIds,Values=$instance_id" \
  --query 'InstanceInformationList[0].PingStatus' --output text
```

The result must be `Online`. If it is empty or `ConnectionLost`, wait 15 seconds and repeat the same read-only query; AWS CLI exposes no `instance-online` waiter.

**Repeat, reset, or rollback**

Read-only and safe to repeat. If user data is corrected, Terraform may replace the disposable instance because `user_data_replace_on_change=true`.

**If it fails**

- SSM offline: verify the instance profile, internet route, public IP assignment, SSM agent service, and user-data log.
- Endpoint failure: verify the subnet, endpoint security group on TCP 443, and VPC DNS support.
- Unexpected ingress: stop and correct Terraform before storing credentials.

**Next**

Generate the two secret values.

## Step 7 — Generate and store database secret values

**Purpose**

Create fresh random credentials outside Terraform and store them without printing them.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- Terraform apply and Step 6 verification passed.
- Both secret containers exist.
- Terminal command tracing is disabled.

**Inputs**

The script resolves the secret names and database private IP from Terraform outputs. Users provide no password.

**Command**

```bash
set +x
make secrets-put
```

**Expected result**

The script generates fresh values with Python `secrets.token_hex`, uploads each JSON document from a mode-restricted temporary directory, deletes the temporary files, and prints only a success message.

**Verify**

Verify metadata without retrieving values:

```bash
aws secretsmanager describe-secret --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --secret-id /aws-glue-postgres-mongodb-lab/postgres --query LastChangedDate --output text
aws secretsmanager describe-secret --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --secret-id /aws-glue-postgres-mongodb-lab/mongodb --query LastChangedDate --output text
```

**Repeat, reset, or rollback**

Re-running `make secrets-put` first proves the current STS account and Region match Terraform state, then deliberately rotates both values. After rotation, rerun `make ec2-bootstrap`; its temporary EC2 `.env` is deleted immediately after startup and tests.

**If it fails**

Confirm `secretsmanager:PutSecretValue` on only the two lab secrets. Do not print, paste, or commit a secret to diagnose the issue.

**Next**

Start and test the databases through SSM.

## Step 8 — Bootstrap and validate PostgreSQL/MongoDB through SSM

**Purpose**

Retrieve secrets on EC2, write a temporary mode-`0600` `.env`, start both pinned containers, run deterministic tests, and delete the environment file immediately without SSH.

**Run from**

`Mac terminal — repository root`; the command executes `scripts/bootstrap-ec2.sh` remotely as `ec2-user`.

**Prerequisites**

- SSM instance status is `Online`.
- Step 7 stored both secret values.
- EC2 user data cloned the selected public branch to `/opt/aws-glue-postgres-mongodb-lab`.

**Inputs**

No password or endpoint input. The Make target resolves the EC2 instance ID from Terraform state.

**Command**

```bash
make ec2-bootstrap
```

**Expected result**

The SSM command succeeds. On EC2 it:

1. fast-forwards the current public branch;
2. retrieves both secrets using the instance role without printing them;
3. writes `.env` with mode `0600` and binds database ports on the EC2 interface;
4. runs `make local-up` and `make local-test`;
5. deletes `.env` immediately on success or failure;
6. records the exact checked-out Git SHA in `.lab-commit-sha`;
7. reports `aws-glue-postgres-mongodb-lab EC2 bootstrap: PASS`.

**Verify**

```bash
instance_id="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"
command_id="<command_id printed by make ec2-bootstrap>"
aws ssm get-command-invocation --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --command-id "$command_id" --instance-id "$instance_id" \
  --query '{Status:Status,Output:StandardOutputContent}' --output json
```

The status must be `Success`. The output includes `git_sha=...`, `temporary environment cleanup: PASS`, the deterministic data assertions, and the final bootstrap pass line. Do not publish the instance ID or container endpoints.

**Repeat, reset, or rollback**

Safe to rerun against unchanged secret values and code. For a clean database reseed, run the project-scoped `make local-down RESET_VOLUMES=1` through SSM, then rerun `make ec2-bootstrap`.

**If it fails**

- Inspect the SSM invocation output, then `/var/log/aws-glue-lab-bootstrap.log`.
- If Docker access is denied, confirm the command runs as `ec2-user` after user data added that account to the Docker group.
- If secret retrieval fails, verify the EC2 role is attached and the secret names are exact.
- If a container fails health checks, continue with [02 — Start Databases](02-START-DATABASES.md) troubleshooting.

**Next**

Optionally configure write access from EC2, or continue to runbook 02.

## Step 9 — Optional EC2 deploy key for feature-branch pushes

**Purpose**

Allow deliberate feature-branch pushes from EC2 without copying the private key off the instance.

**Run from**

`Mac terminal using SSM; key generation runs as ec2-user on EC2`

**Prerequisites**

- SSM is online.
- The user intends to make a reviewed EC2-side change.
- Repository admin permission to add a GitHub deploy key.

**Inputs**

No key material from the Mac.

**Command**

Send the key-generation script through SSM:

```bash
instance_id="$(terraform -chdir=infrastructure/terraform output -raw database_instance_id)"
aws ssm send-command --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --instance-ids "$instance_id" --document-name AWS-RunShellScript \
  --parameters 'commands=["sudo -u ec2-user /opt/aws-glue-postgres-mongodb-lab/scripts/configure-ec2-github-write.sh"]'
```

Copy only the printed `ssh-ed25519 ...` public line into GitHub repository **Settings → Deploy keys**, enable write access, and label it for this disposable lab. Then configure the exact identity and trusted GitHub host keys with:

```bash
aws ssm send-command --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --instance-ids "$instance_id" --document-name AWS-RunShellScript \
  --parameters 'commands=["sudo -u ec2-user env CONFIGURE_REMOTE=1 /opt/aws-glue-postgres-mongodb-lab/scripts/configure-ec2-github-write.sh"]'
```

**Expected result**

The public key is visible once in the SSM invocation output. The private key remains at `/home/ec2-user/.ssh/aws-glue-postgres-mongodb-lab/id_ed25519` with mode `0600`. With `CONFIGURE_REMOTE=1`, the script retrieves GitHub host keys from the TLS-protected GitHub metadata API, writes a private `known_hosts`, sets repository-local `core.sshCommand` to the deploy-key identity, and changes the remote. It never pushes code or `main`.

**Verify**

On EC2 through SSM:

```bash
sudo -u ec2-user test -f /home/ec2-user/.ssh/aws-glue-postgres-mongodb-lab/id_ed25519
sudo -u ec2-user test "$(stat -c '%a' /home/ec2-user/.ssh/aws-glue-postgres-mongodb-lab/id_ed25519)" = 600
sudo -u ec2-user git -C /opt/aws-glue-postgres-mongodb-lab config --get core.sshCommand
sudo -u ec2-user ssh-keygen -F github.com -f /home/ec2-user/.ssh/aws-glue-postgres-mongodb-lab/known_hosts
```

**Repeat, reset, or rollback**

Generation is idempotent. At teardown, delete the GitHub deploy key and destroy EC2. Never download, display, or reuse the private key.

**If it fails**

Confirm the command ran as `ec2-user` and `.ssh` permissions are correct. Do not replace this with a personal GitHub token in `.env`.

**Next**

Continue to [02 — Start and Verify the Databases](02-START-DATABASES.md).

## Step 10 — Review the destroy plan without destroying

**Purpose**

Prove the foundation is disposable and identify cleanup dependencies before later work adds data.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

The live state from Step 5 exists.

**Inputs**

The same personal AWS profile and Region.

**Command**

```bash
terraform -chdir=infrastructure/terraform plan -destroy -out=destroy.tfplan
terraform -chdir=infrastructure/terraform show destroy.tfplan
```

**Expected result**

The destroy plan includes only Terraform-managed, project-tagged lab resources. The S3 bucket uses `force_destroy` so project objects will not strand teardown; the two disposable secrets use zero-day recovery.

**Verify**

Confirm no unrelated AWS resource appears and the plan contains no secret value.

**Repeat, reset, or rollback**

Delete the ignored review artifact after inspection:

```bash
rm -f infrastructure/terraform/destroy.tfplan
```

Do not apply the destroy plan during GLUE-020. Final cleanup and evidence belong to [06 — Destroy](06-DESTROY.md).

**If it fails**

Resolve state drift before adding later Glue resources. Never remove resources manually merely to make the plan shorter.

**Next**

Proceed to [02 — Start and Verify the Databases](02-START-DATABASES.md). Later tasks must not begin until the GLUE-020 PR is reviewed and merged.
