# 00 — Prerequisites

Owner: `GLUE-020`  
Status: implemented by `GLUE-020`

Prepare a clean Mac for the disposable AWS Glue lab without assuming prior Terraform or Glue experience. The core path uses the Mac only as the control machine; PostgreSQL and MongoDB run on one SSM-managed EC2 instance.

> [!WARNING]
> The lab creates billable AWS resources. A focused session should normally remain in the single-digit-dollar range, but pricing and run time vary. Stop before the documented project total approaches USD 25, and complete [06 — Destroy](06-DESTROY.md) when the lab is finished.

## Step 1 — Confirm the Mac and shell

**Purpose**

Record the host architecture and shell before selecting tool packages.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

A personal Mac account with permission to install user tools.

**Inputs**

None.

**Command**

```bash
uname -m
printf '%s\n' "$SHELL"
sw_vers
```

**Expected result**

`uname -m` prints `arm64` on Apple Silicon or `x86_64` on an Intel Mac. The shell is normally `/bin/zsh`.

**Verify**

```bash
case "$(uname -m)" in arm64|x86_64) echo 'architecture: PASS' ;; *) exit 1 ;; esac
```

**Repeat, reset, or rollback**

Read-only; repeat at any time.

**If it fails**

If standard macOS commands are unavailable, repair the local shell before continuing. Do not compensate by running the lab from an unapproved work machine.

**Next**

Install the control-plane tools.

## Step 2 — Install Git, GitHub CLI, AWS CLI v2, Terraform, and Make

**Purpose**

Install only the tools used by the lab.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

- Internet access.
- Homebrew, or permission to install it from [brew.sh](https://brew.sh/).
- Apple Command Line Tools when prompted.

**Inputs**

None.

**Command**

```bash
brew update
brew install git gh awscli make
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

If Homebrew is not allowed, use the vendor-signed AWS CLI v2 installer and the checksum-verified Terraform archive for the Mac architecture. Do not copy binaries from an untrusted mirror.

**Expected result**

All five commands are available. AWS CLI reports major version 2; Terraform satisfies `>= 1.15.0, < 2.0.0`.

**Verify**

```bash
git --version
gh --version
aws --version
terraform version
make --version
```

**Repeat, reset, or rollback**

Homebrew installation is idempotent. Remove a tool with `brew uninstall <formula>` only if the lab no longer needs it.

**If it fails**

- Run `xcode-select --install` if Git or Homebrew reports missing Command Line Tools.
- Reopen the terminal if a newly installed command is not on `PATH`.
- Do not use `sudo pip` or an unverified Terraform wrapper.

**Next**

Authenticate GitHub.

## Step 3 — Authenticate GitHub for normal clone and review work

**Purpose**

Allow the Mac to clone the public repository and use the GitHub CLI. The EC2 core path initially clones over public HTTPS and does not need a GitHub credential.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

A GitHub account authorized for `Korrojo/aws-glue-postgres-mongodb-lab` when push access is needed.

**Inputs**

GitHub login completed in the browser or with the user's normal secure method.

**Command**

```bash
gh auth login
gh auth status
gh repo view Korrojo/aws-glue-postgres-mongodb-lab --json nameWithOwner,visibility
```

**Expected result**

GitHub CLI reports an authenticated account and the repository is `PUBLIC`.

**Verify**

```bash
gh api user --jq .login
```

**Repeat, reset, or rollback**

Use `gh auth logout` to remove the local GitHub session. Never commit a token or copy one to EC2.

**If it fails**

Re-run `gh auth login`. Confirm that the selected account can read the repository. GitHub write access is optional until a reviewed feature branch must be pushed.

**Next**

Configure a personal AWS profile.

## Step 4 — Create or select the personal AWS profile

**Purpose**

Keep this disposable personal lab out of employer or client AWS accounts.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

A personal AWS account and a personal IAM or IAM Identity Center principal with the permissions listed in Step 8.

**Inputs**

Choose a profile name, for example `personal-glue-lab`. Supply credentials only through the AWS CLI's supported configuration flow.

**Command**

For IAM Identity Center:

```bash
aws configure sso --profile personal-glue-lab
aws sso login --profile personal-glue-lab
```

For a personal account that does not use IAM Identity Center:

```bash
aws configure --profile personal-glue-lab
```

Then set the session inputs:

```bash
export AWS_PROFILE=personal-glue-lab
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

**Expected result**

The selected profile resolves credentials without printing or storing them in the repository.

**Verify**

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --output json
aws configure get region --profile "$AWS_PROFILE"
```

Read the returned account and ARN. Continue only if both identify the intended personal account. Stop if the account, role name, or organization belongs to an employer or client.

**Repeat, reset, or rollback**

Unset the session with:

```bash
unset AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION
```

Use `aws configure list-profiles` to select another existing profile. Do not delete unrelated profiles.

**If it fails**

- For SSO, refresh with `aws sso login --profile "$AWS_PROFILE"`.
- For `ExpiredToken`, refresh the personal session rather than adding credentials to `.env`.
- For an unexpected account, stop immediately and select the correct personal profile.

**Next**

Clone and validate the repository.

## Step 5 — Clone the reviewed repository

**Purpose**

Create a clean local checkout and record the code revision used for the lab.

**Run from**

`Mac terminal — the parent directory where the repository should live`

**Prerequisites**

Steps 2–4 completed.

**Inputs**

The public canonical repository URL.

**Command**

```bash
git clone https://github.com/Korrojo/aws-glue-postgres-mongodb-lab.git
cd aws-glue-postgres-mongodb-lab
git switch main
git pull --ff-only
git status --short
git rev-parse HEAD
```

**Expected result**

The checkout is on `main`, `git status --short` prints nothing, and a 40-character commit SHA is recorded in the terminal.

**Verify**

```bash
test "$(git branch --show-current)" = main
test -z "$(git status --short)"
test "$(git remote get-url origin)" = 'https://github.com/Korrojo/aws-glue-postgres-mongodb-lab.git'
```

**Repeat, reset, or rollback**

Use `git pull --ff-only` for reviewed updates. Do not use `git reset --hard` on a checkout with uncommitted work.

**If it fails**

Resolve local changes before continuing. Confirm the remote points to the public canonical repository, not an unreviewed copy.

**Next**

Run the lab doctor.

## Step 6 — Run `make doctor`

**Purpose**

Check the exact repository, tools, Region, and personal AWS identity before Terraform can contact AWS.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- `AWS_PROFILE` selects the personal account.
- `AWS_REGION=us-east-1`.
- Terraform and AWS CLI are on `PATH`.

**Inputs**

The exported profile and Region only.

**Command**

```bash
make doctor
```

**Expected result**

The command prints the personal AWS account/principal, `us-east-1`, the Git SHA, tool versions, and `doctor: PASS`. Docker may be reported as optional and absent.

**Verify**

Manually compare the printed account and principal with the personal account selected in Step 4. Account identifiers are runtime evidence; do not paste them into repository files or PR comments.

**Repeat, reset, or rollback**

Read-only; repeat before every lab session or after changing profiles.

**If it fails**

Follow the exact error. Missing credentials, a non-`us-east-1` Region, or an unexpected identity is a stop condition.

**Next**

Confirm optional local tools and AWS permissions.

## Step 7 — Treat Docker, Python, and Java as optional local tools

**Purpose**

Avoid unnecessary workstation setup.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

None beyond Step 6.

**Inputs**

Choose whether to run the optional Mac container smoke test.

**Command**

```bash
command -v docker || true
command -v python3 || true
command -v java || true
```

**Expected result**

- Docker Desktop is required only for the optional local path in [02 — Start Databases](02-START-DATABASES.md).
- Python 3.11 and Java 17 are required only for later local Glue/unit-test work.
- The core GLUE-020 path works from the Mac without local containers.

**Verify**

```bash
make terraform-check
```

This check needs Terraform and network access to install pinned providers, but no AWS credential or live AWS resource.

**Repeat, reset, or rollback**

Skip optional tools. Do not install Docker Desktop, Python, or Java solely to satisfy `GLUE-020`.

**If it fails**

Confirm Terraform can reach `registry.terraform.io`. Provider versions are locked in `infrastructure/terraform/.terraform.lock.hcl`.

**Next**

Review required AWS permissions and session limits.

## Step 8 — Confirm permissions, time, cost, and cleanup ownership

**Purpose**

Verify the personal principal can create only the documented lab resources and that the operator owns cleanup.

**Run from**

`Mac terminal and AWS console — personal account`

**Prerequisites**

The identity from Step 6 is confirmed personal.

**Inputs**

No repository secret. Obtain any approval required by the owner of the personal AWS account.

**Command**

Review access for these service actions:

- EC2/VPC: VPC, subnet, route, internet gateway, security groups, two VPC endpoints, one `t3.medium` instance, and SSM status.
- IAM: create/delete the two lab roles, instance profile, inline policies, and managed-policy attachments; `iam:PassRole` for the lab roles.
- S3: create/configure/delete one project-tagged bucket and its objects.
- Secrets Manager: create, describe, update, read, and delete only the three project secrets (PostgreSQL, MongoDB bootstrap administrator, and MongoDB connector).
- SSM and public SSM parameters: resolve the Amazon Linux 2023 AMI, send commands, and read invocation status.
- Glue permissions are created for later tasks; `GLUE-020` does not create Glue jobs, crawlers, or connections.

Record a 60–90 minute infrastructure session window. Set a personal budget alert if the account does not already have one.

**Expected result**

The operator understands the resource boundary, the under-USD-25 project guardrail, and the mandatory destroy step.

**Verify**

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --query Arn --output text
printf 'Region=%s\n' "$AWS_REGION"
```

Do not paste the returned account identifier or ARN into tracked files.

**Repeat, reset, or rollback**

Permission review is read-only. If broader administrator access is used in a personal sandbox, keep the Terraform resource scope unchanged and destroy the lab promptly.

**If it fails**

Stop if the principal cannot create, inspect, or delete the listed resources. Do not weaken Terraform safety controls or switch to an employer account.

**Next**

Continue to [01 — Deploy AWS Infrastructure](01-DEPLOY-INFRASTRUCTURE.md).
