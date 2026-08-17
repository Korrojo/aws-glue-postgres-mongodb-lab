# 00 — Prerequisites

Owner: `GLUE-020`; usability correction: `GLUE-070`

Status: implemented by `GLUE-020`; `GLUE-070` revision complete, review pending

Prepare a clean Mac for the disposable AWS Glue lab without assuming prior Terraform or Glue experience. The core path uses the Mac only as the control machine; PostgreSQL and MongoDB run on one SSM-managed EC2 instance.

> [!WARNING]
> The lab creates billable AWS resources. A focused session should normally remain in the single-digit-dollar range, but pricing and run time vary. Stop before the documented project total approaches USD 25, and complete [06 — Destroy](06-DESTROY.md) when the lab is finished.

> [!IMPORTANT]
> Every `aws ...` command in this runbook is **User-run only**. Development
> agents never run it or request access to its credentials.

## Before you begin

This runbook prepares the Mac as the lab's **control machine**. The Mac sends
commands to AWS and holds the local Terraform state. The primary lab databases
do not run on the Mac; Terraform creates one disposable EC2 host, and Docker runs
PostgreSQL and MongoDB there.

The words used below have distinct meanings:

- **Terminal** is the macOS application where commands are entered. Open it from
  Applications > Utilities > Terminal.
- **Command-line tool** is a program such as `git`, `aws`, or `terraform` that is
  invoked from Terminal.
- **AWS CLI profile** is a local name for an AWS authentication configuration.
  Creating a profile does not create an AWS account or IAM user.
- **Environment variable** is a value exported only into the current shell and
  inherited by commands started from that shell. Exporting `AWS_PROFILE` selects
  a profile; it does not create that profile or supply credentials.
- **User-run only** means the reader runs the AWS command. Development agents do
  not request credentials or execute live AWS operations.

Required commands for the primary path: Git, GitHub CLI, AWS CLI v2, Terraform,
GNU Make, and the basic `python3` supplied with the Apple Command Line Tools.
Homebrew is the recommended installer. The specifically pinned Python 3.11,
Docker Desktop, and Java 17 setup is optional unless the reader chooses the
local container or local Spark-test paths.

Run command blocks from top to bottom unless a step explicitly presents
alternative authentication paths. Never paste AWS credentials, GitHub tokens,
account IDs, ARNs, Terraform state, or `.env` contents into repository files,
issues, or pull requests.

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

## Step 2 — Install Homebrew and the required command-line tools

**Purpose**

Install the programs that let the Mac download the repository, authenticate to
GitHub and AWS, describe the AWS infrastructure, and invoke the repository's
repeatable commands.

| Tool | Why this lab uses it |
|---|---|
| Homebrew (`brew`) | Installs and updates the Mac command-line tools from known packages. |
| Git (`git`) | Clones the repository and identifies the exact reviewed commit used for the lab. |
| GitHub CLI (`gh`) | Authenticates the Mac to GitHub and confirms the canonical public repository. |
| AWS CLI v2 (`aws`) | Authenticates the user and performs the documented user-run AWS operations. |
| Terraform (`terraform`) | Creates and later destroys the exact AWS resources described as code. |
| GNU Make (`make`) | Provides short, consistent commands that call the repository scripts. |
| Basic Python (`python3`) | Lets `make doctor` parse the AWS identity response; the optional tests require the separate pinned Python 3.11 setup in Step 7. |

**Run from**

`Mac terminal — any directory`

**Prerequisites**

- Internet access.
- A Mac administrator password may be requested by Apple's or Homebrew's
  installer. Do not enter that password into a repository command or file.

**Inputs**

None. Homebrew automatically chooses `/opt/homebrew` on Apple Silicon and
`/usr/local` on Intel Macs.

**Command**

First check whether Homebrew is already installed:

```bash
command -v brew || true
```

If that command prints no path, install Homebrew using the command published at
[brew.sh](https://brew.sh/):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Read the installer's summary before approving it. At the end, Homebrew prints a
`brew shellenv` command. Copy and run the exact command it prints so that the
current shell can find `brew`, then open a new Terminal window and verify it:

```bash
brew --version
brew doctor
```

Install the required tools:

```bash
brew update
brew install git gh awscli make
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

Homebrew installs GNU Make as `gmake` and keeps the name `make` in a separate
`gnubin` directory to avoid replacing macOS files. Select GNU Make in the current
shell before using this repository:

```bash
export PATH="$(brew --prefix make)/libexec/gnubin:$PATH"
```

To make that selection persistent, add this literal line to `~/.zprofile`, then
open a new Terminal window:

```text
export PATH="$(brew --prefix make)/libexec/gnubin:$PATH"
```

If Homebrew is not allowed, use the vendor-signed AWS CLI v2 installer and the
checksum-verified Terraform archive for the Mac architecture. Do not copy
binaries from an untrusted mirror.

**Expected result**

All required commands are available. `aws --version` begins with `aws-cli/2`;
AWS CLI is at least 2.32.0 so that Step 4 can use `aws login`; Terraform satisfies
`>= 1.15.0, < 2.0.0`; and `make --version` identifies GNU Make.

**Verify**

```bash
git --version
gh --version
aws --version
terraform version
make --version
python3 --version
```

Pass conditions:

- every command exits with status 0;
- `command -v` would find each tool in the current shell;
- no version check reports `command not found`;
- `make --version` does not identify Apple/BSD Make.

**Repeat, reset, or rollback**

Running `brew install` again is safe; Homebrew reports already-installed packages.
Use `brew upgrade` only when intentionally updating tools. Do not uninstall a
tool that another local project may use.

**If it fails**

- **`xcode-select: error` or missing developer tools:** run
  `xcode-select --install`, complete Apple's installer, and repeat this step.
- **`brew: command not found` after installation:** run the `brew shellenv`
  command printed by the installer, open a new Terminal window, and repeat
  `brew --version`.
- **`make --version` shows the macOS-provided version:** repeat the `export PATH`
  command above and verify `command -v make` before continuing.
- **`python3: command not found`:** complete `xcode-select --install`, open a new
  Terminal window, and repeat `python3 --version`. Do not use `sudo pip`.
- **AWS CLI is older than 2.32.0:** run `brew upgrade awscli`, then repeat
  `aws --version`.
- **Terraform is outside the required range:** run
  `brew upgrade hashicorp/tap/terraform`, then repeat `terraform version`.
- Do not use `sudo pip` or an unverified Terraform wrapper.

**Next**

Authenticate GitHub.

## Step 3 — Authenticate GitHub for normal clone and review work

**Purpose**

Allow the Mac to identify the signed-in GitHub user, inspect the canonical
repository, and later push a feature branch when needed. The repository is
public, so cloning does not require authentication; authentication is needed for
review and write operations. The EC2 core path separately clones over public
HTTPS and does not receive the Mac's GitHub credential.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

A GitHub account authorized for `Korrojo/aws-glue-postgres-mongodb-lab` when push access is needed.

**Inputs**

The GitHub username and normal browser sign-in method. No personal access token
needs to be created or pasted for this browser flow.

**Command**

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth status
gh repo view Korrojo/aws-glue-postgres-mongodb-lab --json nameWithOwner,visibility
```

The first command opens a browser. In the browser:

1. Sign in to the intended personal GitHub account if prompted.
2. Confirm the one-time device or authorization request shown by GitHub.
3. Authorize GitHub CLI.
4. Return to Terminal only after the browser reports success.

GitHub CLI stores the resulting token in the macOS credential store when that
store is available. Do not display or copy the token into this repository.

**Expected result**

GitHub CLI reports an authenticated account. The repository query returns
`Korrojo/aws-glue-postgres-mongodb-lab` with visibility `PUBLIC`.

**Verify**

```bash
gh api user --jq .login
```

Pass: the command prints the intended GitHub username and exits with status 0.

**Repeat, reset, or rollback**

It is safe to repeat `gh auth status` and the repository query. Run
`gh auth logout --hostname github.com` only when intentionally removing the local
GitHub session. Never commit a token or copy one to EC2.

**If it fails**

- **Browser does not open:** copy the one-time URL printed by `gh auth login`
  into the browser, complete authorization, and repeat `gh auth status`.
- **Wrong GitHub account:** run `gh auth logout --hostname github.com`, repeat the
  login command, and select the intended account.
- **Repository query returns `Not Found`:** confirm the spelling and that the
  signed-in account can access GitHub. The repository is public, so organization
  membership is not required for read access.
- GitHub write access is optional until a reviewed feature branch must be pushed.

**Next**

Configure a personal AWS profile.

## Step 4 — Create or select the personal AWS profile

**Purpose**

Give AWS CLI and Terraform temporary access to the intended personal AWS
account, under a recognizable local name, while preventing accidental use of an
employer or client account.

Four pieces work together:

| Item | Meaning |
|---|---|
| AWS account or principal | The identity and permissions that AWS evaluates. |
| CLI profile | A local name such as `personal-glue-lab` for one authentication configuration. |
| Saved Region | The profile's default AWS Region; this lab fixes it at `us-east-1`. |
| Shell exports | Values that tell commands in the current Terminal which profile and Region to use. |

Exporting `AWS_PROFILE=personal-glue-lab` selects that name but does not create
the profile. Likewise, exporting `AWS_REGION` does not add credentials. A profile
becomes usable only after one of the supported authentication paths below
succeeds.

**Run from**

`Mac terminal — any directory`

**Prerequisites**

- A personal AWS account that is not owned by an employer or client.
- AWS CLI 2.32.0 or newer for the recommended Console-login path.
- Browser access to the personal AWS Console, or an IAM Identity Center start
  URL if that is how the account is managed.
- The permissions listed in Step 8.

**Inputs**

Use the local profile name `personal-glue-lab`. Choose exactly one authentication
path below. Do not combine paths in the same profile.

**Command — User-run only**

### Path A — Personal AWS Console login, including a root Console user

Use this path when signing in through the ordinary personal AWS Console. It uses
short-lived browser credentials and does not create or store a root access key:

```bash
aws login --profile personal-glue-lab
```

The command opens a browser. In the browser:

1. Select the active session for the intended personal AWS account, or sign in
   to that account.
2. Confirm the account name before approving access. Stop if it belongs to an
   employer or client.
3. Approve the request for AWS CLI local-development access.
4. Return to Terminal after the browser reports success.

AWS supports this temporary flow for a root Console user, but root should be
reserved for account administration. Never create root access keys for this
lab. A later improvement can move routine work to IAM Identity Center without
changing the lab architecture.

### Path B — IAM Identity Center

Use this path only if the personal account already provides an IAM Identity
Center start URL and assigned account/role:

```bash
aws configure sso --profile personal-glue-lab
aws sso login --profile personal-glue-lab
```

The configuration wizard asks for the start URL or issuer URL, SSO Region,
account, role, default client Region, output format, and profile name. Select the
personal account and approved role, use `us-east-1` as the default client Region,
and use `json` as the output format. The login command then opens the browser for
authorization.

### Path C — Existing IAM access keys

Long-lived IAM access keys are not recommended. Use this path only when a
personal IAM user—not the root user—already has separately issued access keys:

```bash
aws configure --profile personal-glue-lab
```

At the prompts, enter the issued access-key ID, issued secret access key,
`us-east-1`, and `json`. The AWS Console password is not an access key and must
never be entered at the secret-access-key prompt. Leaving every prompt blank
does not create a usable profile.

### Save the fixed Region and select the profile

After Path A, B, or C succeeds, save the non-secret settings explicitly:

```bash
aws configure set region us-east-1 --profile personal-glue-lab
aws configure set output json --profile personal-glue-lab
```

Then select the profile and Region for the current Terminal session:

```bash
export AWS_PROFILE=personal-glue-lab
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

**Expected result**

`aws configure list-profiles` includes `personal-glue-lab`.
`aws configure list --profile personal-glue-lab` reports where the profile,
temporary credentials, and Region are resolved. Temporary credential values are
masked and nothing is written to the repository.

**Verify**

```bash
aws configure list-profiles
aws configure list --profile "$AWS_PROFILE"
aws sts get-caller-identity --profile "$AWS_PROFILE" --output json
aws configure get region --profile "$AWS_PROFILE"
```

Pass conditions:

- the profile list contains `personal-glue-lab`;
- credential fields in `aws configure list` are resolved rather than `<not set>`;
- `get-caller-identity` returns `Account`, `Arn`, and `UserId` without an error;
- the account and ARN identify the intended personal account;
- the saved Region prints exactly `us-east-1`.

An ARN ending in `:root` is expected only when Path A intentionally used the
personal root Console session. Stop if the account, role, or organization is not
the personal lab account. Do not paste the account ID or full ARN into tracked
files, issues, or PRs.

**Repeat, reset, or rollback**

The identity and Region commands are read-only and safe to repeat. Temporary
`aws login` credentials are refreshed during the session and expire after the
configured session duration, up to 12 hours.

To remove the Path A cached login and clear the shell selection:

```bash
aws logout --profile personal-glue-lab
unset AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION
```

For Path B, use `aws sso logout` only when intentionally signing out of all SSO
sessions. To clear only the shell selection without deleting a profile, run:

```bash
unset AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION
```

Use `aws configure list-profiles` to select another existing profile. Do not delete unrelated profiles.

**If it fails**

- **`The config profile (personal-glue-lab) could not be found`:** the export
  selected a name that has not been configured. Run Path A or B, save the Region,
  export the variables again, and repeat the verification block.
- **`aws configure` shows four prompts and all were left blank:** no credentials
  were configured. Do not enter a Console password. Use Path A for a normal or
  root Console login, then repeat the verification block.
- **Browser does not open for `aws login`:** run
  `aws login --remote --profile personal-glue-lab`, follow the printed URL and
  authorization-code instructions, then repeat the verification block.
- **`ExpiredToken`:** repeat `aws login --profile "$AWS_PROFILE"` for Path A or
  `aws sso login --profile "$AWS_PROFILE"` for Path B. Never add credentials to
  `.env`.
- **`aws configure get region` prints nothing:** repeat both `aws configure set`
  commands above. The export sets a shell value but this verification command
  reads the saved profile setting.
- **Unexpected account or ARN:** stop immediately, run
  `unset AWS_PROFILE AWS_REGION AWS_DEFAULT_REGION`, and select the correct
  personal profile. Do not continue to Terraform.

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

What these commands do:

- `git clone` downloads the public reviewed repository into a new directory.
- `cd` changes Terminal's working directory to that checkout.
- `git switch main` selects the reviewed default branch used for user-run labs.
- `git pull --ff-only` accepts reviewed updates without creating a surprise
  local merge commit.
- `git status --short` reveals local edits; no output means the checkout is clean.
- `git rev-parse HEAD` prints the exact commit that the later AWS run can be tied
  back to.

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

- **Destination directory already exists:** do not clone over it. Enter the
  existing checkout, run `git status --short`, and preserve any local work before
  deciding whether to update it.
- **Authentication is requested during this public clone:** stop and recheck the
  URL; the canonical read-only HTTPS clone does not need a GitHub token.
- **`git pull --ff-only` refuses to update:** preserve the reported local work
  and branch. Do not use `git reset --hard`; resolve the branch state before
  repeating the clone verification.
- **Remote mismatch:** stop if `git remote get-url origin` is not the canonical
  URL shown above.

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

**Command — User-run only**

```bash
make doctor
```

**Expected result**

The command prints the personal AWS account/principal, `us-east-1`, the Git SHA, tool versions, and `doctor: PASS`. Docker may be reported as optional and absent.

**Verify**

The final line is `doctor: PASS`. Manually compare the printed account and
principal with the personal account selected in Step 4. Account identifiers are
runtime evidence; do not paste them into repository files or PR comments.

**Repeat, reset, or rollback**

Read-only; repeat before every lab session or after changing profiles.

**If it fails**

- **Profile not found or credentials missing:** return to Step 4, complete one
  authentication path, export the three shell variables, and repeat
  `make doctor`.
- **Region is not `us-east-1`:** repeat the saved-region and export commands in
  Step 4, then repeat `make doctor`.
- **Tool missing or wrong version:** return to Step 2, correct the installation,
  and repeat `make doctor`.
- **Unexpected identity:** stop. Unset the AWS variables and select the intended
  personal profile before retrying. Never continue with a work account.

**Next**

Confirm optional local tools and AWS permissions.

## Step 7 — Optionally install Docker Desktop, Python 3.11, and Java 17

**Purpose**

Install only the local runtimes needed for the optional developer checks.
Docker Desktop runs the PostgreSQL and MongoDB Compose stack on the Mac. Python
3.11 runs the repository's unit and Spark transformation tests. Java 17 is the
JVM required by PySpark. None of them is required to provision the core EC2
database host.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- Step 2 completed and `brew --version` succeeds.
- Docker Desktop currently requires macOS 14 or newer; use the EC2 path
  rather than silently substituting another container platform if the Mac is not
  supported.

**Inputs**

Choose one of these optional goals:

- local database smoke test: Docker Desktop only;
- credential-free unit/Spark development checks: Python 3.11 and Java 17;
- all local checks: install all three.

**Command**

First inspect what is already available:

```bash
command -v docker || true
python3.11 --version 2>/dev/null || true
java -version 2>&1 || true
```

### Optional Docker Desktop installation

```bash
brew install --cask docker-desktop
open -a Docker
```

The first launch opens a setup window. Accept Docker's terms, choose the
recommended settings, and enter the Mac administrator password only if macOS
requests permission for Docker's privileged helper or command-line symlinks.
Wait until Docker Desktop reports that the engine is running before continuing.

Verify the client, engine, and Compose plugin:

```bash
docker version
docker compose version
docker run --rm hello-world
```

The final command downloads a small public test image, runs it, prints a success
message, and removes the stopped container. It does not start this lab's
databases.

### Optional Python and Java installation

```bash
brew install python@3.11
brew install --cask temurin@17
```

Homebrew installs the versioned Python command as `python3.11`. Temurin provides
the Java 17 runtime used by PySpark. Open a new Terminal window after installing
the Java cask, then verify both versions:

```bash
python3.11 --version
/usr/libexec/java_home -v 17
java -version
```

If local Python/Spark tests are desired, create a project-specific virtual
environment from the repository root. A virtual environment keeps this lab's
pinned packages separate from macOS and other Python projects:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --requirement requirements/dev.lock --requirement requirements/runtime.lock
```

The prompt normally gains a `(.venv)` prefix. While it is active, `python`,
`pytest`, and `ruff` resolve to the versions installed for this repository. Run
`deactivate` when finished; this leaves `.venv` available for the next session.
Activate it again with `source .venv/bin/activate` before local Python checks.

**Expected result**

- Docker checks report a reachable server and Docker Compose v2; `hello-world`
  exits successfully.
- Python reports version 3.11.x.
- `/usr/libexec/java_home -v 17` prints a JDK path and Java reports major version
  17.
- `python -m pip check` reports `No broken requirements found` while `.venv` is
  active.
- Any skipped optional tool remains absent without blocking the core EC2 path.

**Verify**

For Docker after choosing the local database path:

```bash
make compose-check
```

Pass: Docker Compose validates the lab configuration without starting the
databases. Continue with the optional Mac section in
[02 — Start Databases](02-START-DATABASES.md) when ready.

For Python and Java, activate `.venv` and run:

```bash
source .venv/bin/activate
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
python -m pip check
make format-check
make lint
make unit-test
```

Pass: dependency validation, formatting, lint, and unit tests all exit with
status 0. Do not install Python packages globally with `sudo pip`.

The credential-free infrastructure check remains available without Docker,
Python, or Java:

```bash
make terraform-check
```

This Terraform check needs network access to install pinned providers, but it
uses no AWS credential and creates no live AWS resource.

**Repeat, reset, or rollback**

It is safe to rerun the Homebrew install commands; already-installed packages
are reported. Quit Docker Desktop when it is not needed. Use `make local-down`
as documented in runbook 02 before removing Docker or resetting lab containers.
Running the virtual-environment creation command again preserves the existing
environment; rerunning the locked `pip install` command restores the pinned
dependencies. Skipping all optional tools is valid for the core EC2 path.

**If it fails**

- **`Cannot connect to the Docker daemon`:** open Docker Desktop, wait for the
  engine-running status, then repeat `docker version`.
- **Docker asks for a password:** confirm the dialog is the macOS Docker Desktop
  privileged-helper prompt. Do not enter the password into Terminal output or a
  repository file.
- **`python3.11: command not found`:** run `brew --prefix python@3.11`, confirm
  the formula installed successfully, open a new Terminal, and repeat the
  version command.
- **`ModuleNotFoundError: No module named 'pyspark'`:** activate `.venv`, repeat
  the locked dependency-install command above, run `python -m pip check`, and
  repeat `make unit-test`.
- **Java 17 is not selected:** run
  `export JAVA_HOME="$(/usr/libexec/java_home -v 17)"`, then repeat
  `java -version` in that Terminal.
- **Terraform provider download fails:** confirm the Mac can reach
  `registry.terraform.io`, then repeat `make terraform-check`. Provider versions
  are locked in `infrastructure/terraform/.terraform.lock.hcl`.

**Next**

Review required AWS permissions and session limits.

## Step 8 — Confirm permissions, time, cost, and cleanup ownership

**Purpose**

Understand which AWS services the lab will use, confirm that the selected
personal identity is allowed to use them, reserve enough uninterrupted time,
and accept responsibility for destroying the resources. Terraform limits what
the repository creates; the signed-in principal determines whether AWS permits
those actions.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- `make doctor` ended with `doctor: PASS` for the intended personal account.
- The reader can sign in to that same personal account in the AWS Console if a
  permission or billing setting must be inspected.

**Inputs**

No repository secret. Reserve a focused 60–90 minute infrastructure session and
plan to run the destroy runbook before leaving the lab. If the personal account
has multiple administrators, confirm who will clean up the resources.

**Review before running any mutating AWS command**

The selected identity needs practical create, read, update, and delete access
for the lab-scoped resources below:

- EC2/VPC: VPC, subnet, route, internet gateway, security groups, two VPC endpoints, one `t3.medium` instance, and SSM status.
- IAM: create/delete the two lab roles, instance profile, inline policies, and managed-policy attachments; `iam:PassRole` for the lab roles.
- S3: create/configure/delete one project-tagged bucket and its objects.
- Secrets Manager: create, describe, update, read, and delete only the three project secrets (PostgreSQL, MongoDB bootstrap administrator, and MongoDB connector).
- SSM and public SSM parameters: resolve the Amazon Linux 2023 AMI, send commands, and read invocation status.
- Glue: one Data Catalog database, two connections, one crawler, one on-demand
  Spark job, job/crawler runs, and their status.
- CloudWatch Logs: the lab's Glue and EC2 bootstrap diagnostics.

The Terraform and script guards restrict names, tags, Region, state, and reviewed
plans. Do not compensate for `AccessDenied` by editing those safety boundaries.
If a root Console session is being used, permissions are broad enough, but the
resource scope and mandatory cleanup remain exactly the same. Do not create root
access keys.

Set a personal AWS budget alert in the Billing and Cost Management console if
the account does not already have one. A budget alert warns about spend; it does
not automatically stop running resources.

**Expected result**

The operator can name the services above, has reserved the lab window, knows who
will perform cleanup, and understands that the under-USD-25 project guardrail is
a stop condition—not a spending target.

**Verify — User-run only**

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --query Arn --output text
printf 'Region=%s\n' "$AWS_REGION"
test "$AWS_REGION" = us-east-1
```

Pass: the ARN identifies the intended personal principal, the Region line is
`Region=us-east-1`, and the final command exits with status 0. Do not paste the
returned account identifier or ARN into tracked files.

**Repeat, reset, or rollback**

Permission and identity review is read-only and safe to repeat. If broader
administrator or root access is used in a personal sandbox, keep the Terraform
resource scope unchanged, run only the ordered lab commands, and destroy the lab
promptly.

**If it fails**

- **Unexpected ARN or Region:** stop and return to Step 4. Do not continue until
  the intended personal account and `us-east-1` both pass.
- **Known permission gap:** correct the personal identity's permissions through
  the account's normal administration path before deployment. Do not weaken
  Terraform safety controls or switch to an employer account.
- **No cleanup window or owner:** postpone deployment. Reading the repository and
  running credential-free checks is safe; creating AWS resources is not.

**Next**

Continue to [01 — Deploy AWS Infrastructure](01-DEPLOY-INFRASTRUCTURE.md).

## Authoritative installation and authentication references

- [Homebrew installation](https://docs.brew.sh/Installation)
- [GitHub CLI browser authentication](https://cli.github.com/manual/gh_auth_login)
- [AWS CLI Console login with temporary credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [AWS CLI IAM Identity Center configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)
- [Docker Desktop installation on Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Homebrew Docker Desktop cask](https://formulae.brew.sh/cask/docker-desktop)
- [Homebrew Python 3.11 formula](https://formulae.brew.sh/formula/python@3.11)
- [Homebrew Temurin 17 cask](https://formulae.brew.sh/cask/temurin@17)
