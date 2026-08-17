# Lab Documentation Standard

## Purpose

The README alone is not the lab manual. It introduces the lab, shows the overall sequence, and links to ordered runbooks.

The runbooks must allow someone on a clean Mac Mini to complete the lab without guessing what a command means, where it runs, which value to replace, what success looks like, or how to recover from a common failure.

Documentation is part of implementation. A component is complete when its runbook is complete and its command contract is covered by credential-free static/mock tests. AWS commands are **User-run only** and are not executed by development agents.

Hermes, Codex, and development agents must never request or use AWS credentials. No agent-run live AWS evidence is required. User-run AWS output may be added later only when the user supplies a redacted result; a user-run failure becomes a separate issue/PR.

## Audience

Assume the reader:

- is comfortable copying terminal commands;
- has a personal AWS account and GitHub account;
- understands basic database concepts;
- may be new to AWS Glue, Terraform, Glue crawlers, Glue connections, Systems Manager, and the MongoDB Glue sink;
- must not be required to infer missing commands from source code.

Do not assume prior knowledge of this repository or a previous lab.

## Core lab sequence

Document one primary path:

```text
prerequisites
  -> deploy AWS infrastructure
  -> create secrets
  -> start PostgreSQL and MongoDB on EC2
  -> deploy Glue code
  -> run crawler
  -> run migration
  -> validate
  -> rerun test
  -> destroy
```

Optional developer paths, such as running containers on the Mac or pushing a feature branch from EC2, must be labeled **Optional** and must not interrupt the primary path.

## Required structure for every runnable step

Every runnable step uses this structure.

### Step N — Action-oriented title

**Purpose**

One or two sentences explaining what the step accomplishes and why it is required for this lab.

**Run from**

State one exact location:

- `Mac Mini terminal — repository root`
- `Mac Mini terminal — infrastructure/terraform`
- `EC2 through Systems Manager Session Manager`
- `AWS console — Glue > Crawlers`

Do not mix locations in one command block.

**Prerequisites**

List observable conditions, not vague dependencies. Examples:

- `aws sts get-caller-identity` succeeds with the personal AWS account.
- `AWS_REGION` is `us-east-1`.
- Terraform apply completed.
- EC2 SSM status is `Online`.
- PostgreSQL and MongoDB container health checks pass.

**Inputs**

Define every value the reader must supply. Prefer a preceding export command over angle-bracket placeholders scattered through commands.

```bash
export AWS_PROFILE="personal-glue-lab"
export AWS_REGION="us-east-1"
```

Never use unexplained placeholders such as `<bucket>`, `<id>`, `CHANGE_ME`, or `REPLACE_ME`.

**Command**

Provide an exact copy/paste command from the stated location.

```bash
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" make doctor
```

Commands must:

- use repository-relative paths;
- quote variables;
- avoid deprecated syntax;
- avoid printing secrets;
- avoid `...` or omitted required flags;
- state whether multiple commands are one block or separate actions.

**Expected result**

Describe stable output characteristics, not account-specific IDs.

Example:

```text
The command exits with status 0 and prints the resolved AWS account,
us-east-1, required tool versions, and "doctor: PASS".
```

**Verify**

Provide a separate command or observable check and define the pass condition.

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

```text
Pass: the Account value is the intended personal AWS account and no AccessDenied error appears.
```

Do not use “verify that it worked” without the verification command and pass condition.

**Repeat, reset, or rollback**

State what happens if the command is run again and how to return to a known state.

Examples:

- Safe to rerun; Terraform reports no changes.
- Rerunning replaces the target document with the same `_id`.
- Run `make local-down` before repeating initialization.
- Do not rerun secret creation unless rotating the disposable lab passwords.

**If it fails**

Include only the most likely failures for that exact step. For each failure provide:

- recognizable error text or symptom;
- probable cause;
- one diagnostic command;
- one corrective action;
- a command to repeat the failed step.

Link uncommon problems to `07-TROUBLESHOOTING.md`.

**Next**

Link the next numbered step.

## Explanation requirements

Before first use, briefly explain:

- why Glue needs VPC connectivity to the EC2 databases;
- the difference between a Glue connection, crawler, Data Catalog table, and Glue job;
- why PostgreSQL rows become nested MongoDB documents;
- why deterministic `_id` supports rerun testing;
- why reconciliation checks both order and item counts;
- why CDC is not part of this version.

Keep explanations tied to the command being run. Do not add a generic AWS textbook chapter.

## Prerequisite documentation requirements

`00-PREREQUISITES.md` must include exact installation and verification instructions for every tool actually required on the Mac Mini. At minimum evaluate:

- Git;
- GitHub authentication for pushing from the Mac;
- AWS CLI v2;
- Terraform;
- GNU Make or the chosen command wrapper;
- Python and Java only if local tests require them;
- Docker Desktop only if the primary or optional local path uses it.

Do not make Docker Desktop a core prerequisite merely because the databases use Docker on EC2.

For AWS access, document:

- how to select the personal AWS profile;
- how to set `us-east-1`;
- how to run `aws sts get-caller-identity`;
- how to recognize accidentally selected work credentials;
- required service permissions at a practical lab level without building an enterprise IAM onboarding system.

## README requirements

The root README must contain:

1. lab objective;
2. what will be created;
3. a compact architecture diagram;
4. approximate time and cost warning;
5. the ten-step primary sequence;
6. prerequisite summary;
7. links to every ordered runbook;
8. a prominent destroy reminder;
9. current implementation status.

The README must not contain a second, shorter set of operational commands that can drift from the runbooks.

## Troubleshooting requirements

Troubleshooting must preserve the lab design. It must not respond to a connection failure by adding:

- a NAT Gateway;
- public database ingress;
- an SSH bastion;
- a load balancer;
- a second database host;
- Kubernetes;
- an alternate ETL engine;
- a production certificate system.

Troubleshooting order:

1. confirm the current step's prerequisites;
2. inspect the exact resource/status involved;
3. inspect relevant logs;
4. correct configuration or restart the disposable component;
5. repeat the failed step;
6. destroy and rebuild only when the simpler correction is insufficient.

## Documentation acceptance checks

A PR that adds or changes a runnable command fails documentation review when any answer below is “no”:

- Does the reader know where to run it?
- Are all prerequisites observable?
- Are all inputs defined?
- Is the command complete and copyable?
- Is expected success described?
- Is there a verification command and pass condition?
- Is rerun/reset behavior stated?
- Are likely failures diagnosed without architectural expansion?
- Is AWS execution clearly labeled **User-run only**, with development verification limited to static/mock/unit/container evidence?

No `TODO`, placeholder instruction, stale command, or untested command contract may remain when the owning component task is marked `DONE`. User-run AWS results are explicitly outside agent development completion.

## Example: unacceptable and acceptable instructions

Unacceptable:

```text
Configure AWS and deploy the infrastructure. Verify that EC2 is running.
```

Acceptable pattern:

```markdown
### Step 2 — Confirm the personal AWS account

**Run from:** Mac Mini terminal — repository root

**Prerequisites:** AWS CLI v2 is installed and the `personal-glue-lab` profile exists.

**Command:**

    export AWS_PROFILE="personal-glue-lab"
    export AWS_REGION="us-east-1"
    aws sts get-caller-identity --profile "$AWS_PROFILE"

**Expected result:** The command returns JSON containing Account, Arn, and UserId.

**Verify:** Confirm Account is the personal account before continuing. Stop if the Arn belongs to a work role.

**Repeat/reset:** Safe to rerun; this command is read-only.

**If it fails:** Run `aws configure list --profile "$AWS_PROFILE"`. Correct the profile credentials, then repeat the command.
```
