# 06 — Destroy the Lab

Owner: `GLUE-025` reviewed-plan safety plus `GLUE-060`; usability correction by `GLUE-110`
Status: implementation complete

> **User-run only:** Agents never request or use AWS credentials and never execute this flow. The user runs it only from the completed reviewed clone. Credential-free fake-boundary tests establish development acceptance; live output is optional user evidence and must be redacted.

Stopping EC2 is not cleanup. Interface endpoints, S3, Secrets Manager, Glue, IAM, networking, and storage remain until the exact reviewed Terraform destroy plan removes them.

Safe cleanup has four separate controls:

| Control | Why it exists |
|---|---|
| Expected-resource inventory | Confirms the fixed lab categories are visible before anything is removed; it is not a price quote |
| Saved destroy plan | The plan is the exact saved instruction set Terraform may apply; review it before approval |
| Private identity metadata | Binds that plan to this repository, state, resource set, personal identity, Region, Git revision, and plan-file hash |
| Post-destroy verification | Performs read-only exact-tag/name checks after Terraform state is empty so a known billable resource is not silently left behind |

Planning does not destroy anything. Applying the reviewed plan is irreversible, and changing the checkout, state, identity, resource set, Region, or plan bytes invalidates the approval.

> [!CAUTION]
> Destruction has no database-volume recovery path. Use only the intended personal account in `us-east-1`. Never publish account IDs, principal ARNs, instance IDs, bucket names, public IPs, secret values, credentialed URIs, Terraform state, plans, or private plan metadata.

## Step 1 — Confirm exact state, identity, and checkout

**Purpose**

Fail before inventory or planning if the repository, Terraform root/state/workspace, profile, account, Region, or endpoint configuration is not the fixed lab target.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- Runbooks 00–05 completed or the user intentionally chose early cleanup.
- `infrastructure/terraform/terraform.tfstate` is the original non-symlink local state used to apply this lab.
- The tree is clean and the selected profile is the intended personal account.

**Inputs**

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
unset AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_ROLE_SESSION_NAME
unset AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
unset AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
unset AWS_ENDPOINT_URL
unset TF_WORKSPACE TF_DATA_DIR TF_CLI_ARGS
unset TF_CLI_ARGS_plan TF_CLI_ARGS_apply TF_CLI_ARGS_destroy TF_CLI_ARGS_state
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="us-east-1"
```

Unset every `AWS_ENDPOINT_URL_*` variable too; scripts reject even an empty override.

**Command — User-run only**

```bash
test "$(pwd -P)" = "$(git rev-parse --show-toplevel)"
test "$(basename "$(pwd -P)")" = aws-glue-postgres-mongodb-lab
test -f infrastructure/terraform/terraform.tfstate
test ! -L infrastructure/terraform/terraform.tfstate
test -z "$(git status --short)"
test "$(terraform -chdir=infrastructure/terraform workspace show)" = default
make doctor
```

**Expected result**

Every test exits `0`; `make doctor` ends in `doctor: PASS` for the intended personal identity and `us-east-1`. No identity value is copied to tracked files.

**Verify — User-run only**

```bash
test "$(terraform -chdir=infrastructure/terraform output -raw aws_region)" = us-east-1
terraform -chdir=infrastructure/terraform state list >/dev/null
printf '%s\n' 'destroy prerequisites: PASS'
```

Pass: `destroy prerequisites: PASS` prints. Do not publish the state list.

**Repeat, reset, or rollback**

Read-only and safe to repeat. Missing/wrong state, a non-default workspace, or wrong account is a hard stop; do not import, remove, or reconstruct state to bypass the binding.

**If it fails**

Use `git status --short`, `terraform -chdir=infrastructure/terraform workspace show`, and `aws configure list --profile "$AWS_PROFILE"`. Return to the original checkout/profile/state. Never delete by tag pattern, VPC scope, wildcard, or account scope.

**Next**

Inventory expected lab resources before destruction.

## Step 2 — Record the expected-resource cost inventory

**Purpose**

List counts for only the resources this lab expects, without Cost Explorer, a dashboard, prices, identifiers, or broad mutation.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 1 passes and the lab state still contains its managed resources.

**Inputs**

`APPROVE_LAB_COST_CHECK=1` explicitly approves read-only AWS inventory. The same profile and Region remain selected.

**Command — User-run only**

```bash
APPROVE_LAB_COST_CHECK=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make cost-check
```

**Expected result**

The command prints redacted JSON counts for Terraform addresses, exact project tags, one EC2 instance, two VPC endpoints, one Glue job, one crawler, two connections, one catalog database, three secrets, two roles, and one artifact bucket. It ends `cost-check: PASS`. It never calls Cost Explorer.

**Verify — User-run only**

```bash
APPROVE_LAB_COST_CHECK=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make cost-check \
  | python3 -c 'import json,sys; line=next(x for x in sys.stdin if x.startswith("{")); assert json.loads(line)["passed"]'
```

Pass: the pipeline exits `0`. Keep output local or publish only the category/count JSON.

**Repeat, reset, or rollback**

Read-only and safe to repeat before destroy. An incomplete expected inventory is a hard stop for diagnosis; it is not permission to discover and remove unrelated resources.

**If it fails**

Confirm the exact Terraform state/profile/Region, then repeat. `AccessDenied` means the personal lab principal lacks a required read action; correct that permission narrowly. Do not add Cost Explorer or account-wide cleanup rights.

**Next**

Create and review the bound destroy plan.

## Step 3 — Create and review the saved destroy plan

**Purpose**

Create one plan bound to the exact project/root/state lineage and serial/resource set/account/principal/profile/Region/Git SHA and plan hash.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Steps 1–2 pass; no unrelated plan is under review.

**Inputs**

The exported personal profile and fixed Region. No approval variable is set during planning.

Capture two values in shell memory so a read-only verification retry remains possible after Terraform outputs disappear. Do not print them:

```bash
export EXPECTED_AWS_ACCOUNT="$(terraform -chdir=infrastructure/terraform output -raw aws_account_id)"
export EXPECTED_ARTIFACT_BUCKET="$(terraform -chdir=infrastructure/terraform output -raw artifact_bucket_name)"
```

**Command — User-run only**

```bash
make destroy-plan
terraform -chdir=infrastructure/terraform show destroy.tfplan
```

**Expected result**

`make destroy-plan` verifies exact state and identity, then writes ignored `destroy.tfplan` and mode-`0600` `.destroy.tfplan.identity.json`. `terraform show` contains only destroy actions for known lab state addresses.

**Verify**

```text
[ ] Operation is destroy and the plan contains no create/update/import/forget action.
[ ] Every address belongs to this lab's reviewed Terraform state.
[ ] No unrelated target appears.
[ ] No secret/state/plan/live identifier will be copied to public evidence.
[ ] The displayed destroy count matches the reviewed address set.
```

Pass: every checkbox is satisfied. Stop on any unfamiliar address.

**Repeat, reset, or rollback**

Re-running `make destroy-plan` replaces plan and identity metadata together. To abandon without mutation:

```bash
rm -f infrastructure/terraform/destroy.tfplan \
  infrastructure/terraform/.destroy.tfplan.identity.json
```

Any Git/state/resource/profile/Region/account/plan-byte change requires a fresh plan and review.

**If it fails**

On identity/state mismatch, select the original values. On drift, inspect a normal Terraform plan and correct only the known state issue. Never approve an unfamiliar target.

**Next**

Consume only the reviewed plan.

## Step 4 — Apply the reviewed plan and run final known-service checks

**Purpose**

Destroy exactly the reviewed state and then fail nonzero if a known project-tagged or exact-named resource remains.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Every Step 3 checkbox passes; plan/metadata/Git/state/profile/account/Region are unchanged; `EXPECTED_AWS_ACCOUNT` and `EXPECTED_ARTIFACT_BUCKET` remain only in shell memory.

**Inputs**

`APPROVE_LAB_DESTROY=1` is the one-command destructive approval.

**Command — User-run only**

```bash
APPROVE_LAB_DESTROY=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make destroy-lab
```

**Expected result**

Before mutation, the script revalidates every reviewed binding and plan hash. It executes only `terraform apply -input=false destroy.tfplan`, never a newly generated plan or `terraform destroy`. After state is empty, `scripts/verify-destroyed.sh` performs read-only exact-tag/name checks for EC2 instances, VPC endpoints, the artifact bucket, Glue job/crawler/connections/database, three secrets, two roles, and the Resource Groups Tagging API. Success prints all-zero category counts, `post-destroy known-service verification: PASS`, and `destroy verification: PASS`.

The reviewed plan and private metadata are consumed after every apply attempt, including partial failure. A retry always needs a new plan review.

**Verify — User-run only**

```bash
test -z "$(terraform -chdir=infrastructure/terraform state list)"
test ! -e infrastructure/terraform/destroy.tfplan
test ! -e infrastructure/terraform/.destroy.tfplan.identity.json
APPROVE_LAB_DESTROY_VERIFY=1 \
EXPECTED_AWS_ACCOUNT="$EXPECTED_AWS_ACCOUNT" \
EXPECTED_ARTIFACT_BUCKET="$EXPECTED_ARTIFACT_BUCKET" \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" ./scripts/verify-destroyed.sh
```

Pass: every command exits `0` and final counts remain zero. The standalone verifier is read-only and exact-scoped; it never deletes a resource.

**Repeat, reset, or rollback**

A successful destroy cannot be repeated with the consumed plan. If Terraform partially fails and state retains addresses, create/review a new smaller destroy plan. If state is empty but final inventory is temporarily nonzero, make one bounded retry after 30 seconds using only the standalone read-only verifier and the two shell-memory bindings:

```bash
sleep 30
APPROVE_LAB_DESTROY_VERIFY=1 \
EXPECTED_AWS_ACCOUNT="$EXPECTED_AWS_ACCOUNT" \
EXPECTED_ARTIFACT_BUCKET="$EXPECTED_ARTIFACT_BUCKET" \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" ./scripts/verify-destroyed.sh
```

Pass: all category counts are zero. If the retry still reports a known remainder, stop and use the exact troubleshooting entry; do not loop or delete broadly. There is no database rollback.

**If it fails**

- Before apply: correct the exact binding and create/review a fresh plan.
- Partial apply with residual state: inspect only `terraform state list` and the Terraform error, then replan/review.
- Empty state but known remainder: use the exact read-only command in [07 — Troubleshooting](07-TROUBLESHOOTING.md). Do not perform wildcard/tag/VPC/account cleanup. A genuine out-of-state remainder requires a separately reviewed exact resolution.
- Access denied during final checks: fix only the named read permission, then repeat the standalone verifier.

**Next**

Remove local sensitive artifacts and, only if used, retire the optional GitHub deploy key.

## Step 5 — Remove local artifacts and optional external access

**Purpose**

Confirm generated local material is absent and remove the one manually managed GitHub deploy key only when the optional EC2 write path was used.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

Step 4 passes or its failure is recorded honestly. `gh auth status` succeeds only if the optional deploy key existed.

**Inputs**

For the optional key only, set the public repository and numeric deploy-key ID shown under GitHub repository **Settings > Deploy keys**:

```bash
export GITHUB_REPOSITORY="Korrojo/aws-glue-postgres-mongodb-lab"
export DEPLOY_KEY_ID="the-numeric-id-from-repository-settings"
```

Do not set these variables if the optional write workflow was never used.

**Command**

Core local cleanup verification:

```bash
test ! -e .env
test ! -e infrastructure/terraform/destroy.tfplan
test ! -e infrastructure/terraform/.destroy.tfplan.identity.json
git status --short
unset EXPECTED_AWS_ACCOUNT EXPECTED_ARTIFACT_BUCKET
```

Optional GitHub cleanup — User-run only, run only if that deploy key existed:

```bash
gh api --method DELETE "repos/$GITHUB_REPOSITORY/keys/$DEPLOY_KEY_ID"
```

**Expected result**

Core tests exit `0`; Git lists no generated secret/state/plan artifact. Optional GitHub deletion exits `0`. The EC2 private key already disappeared with the instance and was never returned or committed; the GitHub deploy-key registration is the only manually removed external resource.

**Verify**

```bash
git check-ignore infrastructure/terraform/terraform.tfstate \
  infrastructure/terraform/destroy.tfplan \
  infrastructure/terraform/.destroy.tfplan.identity.json
```

Optional GitHub verification — User-run only:

```bash
test "$(gh api "repos/$GITHUB_REPOSITORY/keys" --jq \
  "[.[] | select(.id == ($DEPLOY_KEY_ID | tonumber))] | length")" = 0
```

Pass: ignored local paths are reported and, if applicable, the selected key count is zero.

**Repeat, reset, or rollback**

Local checks are safe to repeat. GitHub deletion is not repeatable after the key is gone; create a new key through the optional workflow only for a future lab. Do not remove unrelated repository keys.

**If it fails**

Use `git status --short --ignored` to identify only known generated artifacts. For GitHub `404`, confirm repository/key ID and whether the key is already absent. Never print private key material.

**Next**

The lab is complete. Keep any user-run evidence separate, counts-only/redacted, and clearly labeled as user supplied.
