# 06 — Destroy the Lab

Owner: `GLUE-025` for the current Terraform-managed foundation; final cross-service cleanup remains `GLUE-060`
Status: foundation destroy implemented by `GLUE-025`

> **User-run only:** Agents must never request or use AWS credentials or execute this destroy flow. No agent-run live AWS evidence is required; development uses static/mock/Terraform/unit/container checks. A later user-run failure belongs in a separate issue/PR.

Stopping EC2 is not cleanup. The VPC endpoints, S3 bucket, secrets, IAM resources, networking, and EC2 instance remain until Terraform removes them. This corrective runbook destroys and verifies only the resources currently managed by the exact local foundation state. `GLUE-060` final cost inventory, later Glue resource verification, optional GitHub deploy-key retirement, and complete cross-service project-tag scan are explicitly deferred.

> [!CAUTION]
> These steps are destructive and have no database-volume recovery path. Use only the intended personal AWS account in `us-east-1`. Keep evidence local until redacted. Never publish AWS account IDs, principal ARNs, instance IDs, public IP addresses, secret values, credentialed connection strings, live endpoints, Terraform state, saved plans, or plan metadata. Do not fabricate evidence: report only commands actually run and outputs actually observed, with every failure, skip, and limitation stated.

## Step 1 — Confirm the exact project and local state

**Purpose**

Fail before plan creation if the operator, repository, Terraform root, Region, or local state is not the fixed foundation lab target.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- The lab was applied from this checkout and its local `infrastructure/terraform/terraform.tfstate` remains available.
- The repository working tree is clean.
- The selected profile is the intended personal account.
- The personal-account live-validation sequence has already completed `make doctor`, `make infra-plan`, review the saved infrastructure plan, approved `APPROVE_LAB_APPLY=1 make infra-apply`, `APPROVE_LAB_SECRETS=1 make secrets-put`, and `make ec2-bootstrap` in that order.

**Inputs**

Unset ambient credential sources so both AWS CLI and Terraform must use the approved profile. Then set the personal profile and fixed Region; replace `personal-glue-lab` only with the local profile name for the intended personal account:

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
unset AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_ROLE_SESSION_NAME
unset AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
unset AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
unset TF_WORKSPACE TF_DATA_DIR TF_CLI_ARGS
unset TF_CLI_ARGS_plan TF_CLI_ARGS_apply TF_CLI_ARGS_destroy TF_CLI_ARGS_state
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="us-east-1"
```

**Command**

```bash
test "$(pwd -P)" = "$(git rev-parse --show-toplevel)"
test "$(basename "$(pwd -P)")" = aws-glue-postgres-mongodb-lab
test -f infrastructure/terraform/terraform.tfstate
test ! -L infrastructure/terraform/terraform.tfstate
test -z "$(git status --short)"
make doctor
```

**Expected result**

Every `test` exits `0`, and `make doctor` ends with `doctor: PASS` for the intended personal identity and `us-east-1`. The guarded destroy scripts additionally reject any remaining `TF_CLI_ARGS_*` variable, require Terraform workspace `default`, and compare the active state lineage/serial with the exact local `terraform.tfstate`. No state or identity value is copied into tracked files.

**Verify**

```bash
test "$(terraform -chdir=infrastructure/terraform output -raw aws_region)" = us-east-1
test "$(terraform -chdir=infrastructure/terraform output -raw postgres_secret_name)" = /aws-glue-postgres-mongodb-lab/postgres
test "$(terraform -chdir=infrastructure/terraform output -raw mongodb_secret_name)" = /aws-glue-postgres-mongodb-lab/mongodb
test "$(terraform -chdir=infrastructure/terraform output -raw mongodb_glue_secret_name)" = /aws-glue-postgres-mongodb-lab/mongodb-glue
terraform -chdir=infrastructure/terraform state list
```

Pass: the four `test` commands exit `0`, and the state list contains the expected current resources, including `aws_vpc.lab`, `aws_instance.database_host`, and all three secret containers. Do not publish the full list when it contains live identifiers in indexed instances.

**Repeat, reset, or rollback**

The checks are read-only and safe to repeat. A missing or wrong state is a hard stop; do not import, remove, or reconstruct state merely to bypass the identity gate.

**If it fails**

- Wrong directory or dirty tree: return to the exact checkout and commit or deliberately revert the intended source changes before planning.
- Wrong profile/Region: run `aws configure list --profile "$AWS_PROFILE"`, correct the personal session, then repeat this step.
- Missing state: locate the original ignored local state backup. Do not use broad AWS deletion commands.

**Next**

Create the review-bound destroy plan.

## Step 2 — Create and review the saved destroy plan

**Purpose**

Produce one reviewable plan bound to this exact project, Terraform state identity, personal account, profile, Region, Git SHA, and plan hash before any destructive mutation.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 1 passed, the local state contains current foundation resources, and no unrelated plan is under review.

**Inputs**

The exported `AWS_PROFILE` and `AWS_REGION=us-east-1`. No approval variable is set during planning.

**Command**

```bash
make destroy-plan
terraform -chdir=infrastructure/terraform show destroy.tfplan
```

**Expected result**

`make destroy-plan` first verifies Terraform workspace `default` and proves the active state lineage/serial match the exact local `terraform.tfstate`. It then reports project/state and AWS/state identity passes and saves ignored `destroy.tfplan` plus mode-`0600` `.destroy.tfplan.identity.json`. The metadata identifies the operation as `destroy` and binds the exact roots, state lineage and serial, state resource-set hash, account/principal, profile, Region, Git SHA, and destroy-plan SHA-256. `terraform show` displays destroy actions only for resources currently managed by this foundation state.

**Verify**

Review the saved destroy plan before approval:

```text
[ ] The header identifies a destroy plan for the current local state.
[ ] Every planned action removes a known aws-glue-postgres-mongodb-lab foundation resource.
[ ] No create, update, import, forget, or unrelated resource action appears.
[ ] No secret value, credentialed URI, public IP, account ID, or principal ARN will be copied into public evidence.
[ ] The plan summary's destroy count matches the set reviewed on screen.
```

Pass: every checkbox is satisfied. Stop on any unfamiliar target; there is no approval-by-default.

**Repeat, reset, or rollback**

Re-running `make destroy-plan` replaces the plan and private metadata together. To abandon it without touching AWS:

```bash
rm -f infrastructure/terraform/destroy.tfplan \
  infrastructure/terraform/.destroy.tfplan.identity.json
```

Any Git, state, resource-set, profile, Region, account, or plan-byte change invalidates review and requires a new plan.

**If it fails**

- `ERROR: ... does not match Terraform state`: stop and select the original personal profile/Region or state.
- State drift: inspect a normal `terraform -chdir=infrastructure/terraform plan`; correct only the known foundation issue, then recreate and rereview the destroy plan.
- Unfamiliar resource: do not approve. Record the address without live values and resolve ownership first.

**Next**

Consume only the reviewed saved plan through the explicit approval gate.

## Step 3 — Apply only the reviewed destroy plan

**Purpose**

Destroy exactly the reviewed Terraform-managed foundation resources, with no broad service sweep or newly generated plan.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Every Step 2 review checkbox is satisfied.
- The same clean Git SHA, local state, personal account, profile, and Region remain selected.
- `destroy.tfplan` and `.destroy.tfplan.identity.json` are unchanged.

**Inputs**

The explicit one-command approval variable `APPROVE_LAB_DESTROY=1`.

**Command**

```bash
APPROVE_LAB_DESTROY=1 make destroy-lab
```

**Expected result**

Before AWS mutation, the script rechecks the exact repository and Terraform roots, fixed project configuration, non-symlink local state, state lineage/serial/resource-set hash, destroy operation, account/principal, profile, `us-east-1`, Git SHA, and plan hash. It invokes `terraform apply -input=false destroy.tfplan`, never an unreviewed `terraform destroy`. Success ends with `destroy verification: PASS` after Terraform state contains no managed resource address. The consumed plan and metadata are removed after every apply attempt, including a partial failure, so any retry requires a fresh plan review.

**Verify**

```bash
test -z "$(terraform -chdir=infrastructure/terraform state list)"
test ! -e infrastructure/terraform/destroy.tfplan
test ! -e infrastructure/terraform/.destroy.tfplan.identity.json
```

Pass: all three commands exit `0`. This is the required step to confirm Terraform-managed resource removal for the current foundation.

**Repeat, reset, or rollback**

A successful run cannot be repeated with the consumed plan. Rebuilding requires a new reviewed infrastructure plan and apply. Terraform may leave an empty local state file and `.terraform/` provider cache; both remain ignored. There is no rollback for destroyed disposable databases.

**If it fails**

- Identity/hash failure before apply: make no manual deletion. Re-run Step 1, create a fresh destroy plan, review it, then retry this step.
- Partial Terraform failure: run `terraform -chdir=infrastructure/terraform state list`, inspect only the reported remaining address and Terraform error, then run `make destroy-plan` again against that exact residual state. Review the smaller saved plan before another approved `make destroy-lab`.
- Never delete by tag pattern, wildcard, VPC scope, or account scope to force success.

**Next**

Verify local sensitive artifacts are absent and record the intentionally deferred final checks.

## Step 4 — Verify local cleanup and record deferred final scope

**Purpose**

Confirm that generated sensitive files are absent and distinguish this foundation proof from the final `GLUE-060` cross-service cleanup evidence.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 3 passed or a partial failure has been recorded honestly.

**Inputs**

No additional input.

**Command**

```bash
test ! -e .env
test ! -e infrastructure/terraform/destroy.tfplan
test ! -e infrastructure/terraform/.destroy.tfplan.identity.json
git status --short
```

**Expected result**

The temporary environment, reviewed destroy plan, and private metadata are absent. Git does not list Terraform state, plan, metadata, `.terraform/`, `.lab-commit-sha`, credentials, or secret material. An empty ignored local Terraform state file and ignored provider cache may remain.

**Verify**

```bash
git check-ignore infrastructure/terraform/terraform.tfstate \
  infrastructure/terraform/destroy.tfplan \
  infrastructure/terraform/.destroy.tfplan.identity.json
```

Pass: Git reports all three paths as ignored. No generated sensitive artifact is staged or tracked.

**Repeat, reset, or rollback**

Safe to repeat. Remove only known local generated plan/metadata or `.env` files; do not delete source, the local state needed to recover a partial destroy, or unrelated credentials.

**If it fails**

Use `git status --short --ignored` to identify the exact local artifact. Remove only a known generated secret/plan artifact. Never print its contents while diagnosing.

**Next**

`GLUE-060` remains responsible for final cost inventory, later Glue job/crawler/connection checks, optional GitHub deploy-key removal, broad known-service project-tag verification, the full clean-checkout run, and redacted release evidence. Those cross-service steps are deferred and must not be claimed from this foundation-only run.
