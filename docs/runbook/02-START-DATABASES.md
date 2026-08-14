# 02 — Start and Verify the Databases

Owners: `GLUE-010`, finalized by `GLUE-020`; rotation correction by `GLUE-025`
Status: implemented by `GLUE-010` and `GLUE-020`

PostgreSQL and MongoDB run together on the disposable EC2 instance for the core lab. The Mac path at the end is optional and exists only for a quick developer smoke test. Both paths use the same Compose file, initialization scripts, deterministic fixtures, and assertions.

## Recommended automated EC2 path

**Purpose**

Run the complete secret retrieval, startup, health, fixture, and commit-SHA checks through Systems Manager without opening SSH.

**Run from**

`Mac terminal — repository root`

**Prerequisites**

- Runbook 01 applied and verified the GLUE-020 foundation.
- Both secret values exist.
- The EC2 instance is `Online` in Systems Manager.

**Inputs**

The personal `AWS_PROFILE` and `AWS_REGION=us-east-1`; no database credential is entered or printed.

**Command**

```bash
make ec2-bootstrap
```

**Expected result**

The SSM invocation ends with `aws-glue-postgres-mongodb-lab EC2 bootstrap: PASS`, both containers are healthy, deterministic counts pass, all invalid fixtures are rejected, `.lab-commit-sha` matches the EC2 checkout, and the temporary `.env` is absent.

**Verify**

Use the SSM invocation output and the read-only commands in runbook 01 Step 8. Do not publish the instance ID, private address, endpoints, or secret values.

**Repeat, reset, or rollback**

The command is safe to rerun while secret values are unchanged. After `make secrets-put` rotates values for initialized named volumes, run `make ec2-reset-data`; `make ec2-bootstrap` alone does not rotate credentials stored inside those volumes.

**If it fails**

Continue with the manual diagnostic steps below; they expose each prerequisite and command separately without changing the architecture.

**Next**

After success, retain the recorded Git SHA. Continue to runbook 03 only after `GLUE-025` is reviewed and its personal-account live-validation sequence succeeds.

## Manual EC2 diagnostic path

### Step 1 — Confirm the reviewed repository checkout

**Purpose**

Confirm that the EC2 host is using reviewed `main` code and record the exact commit used for the lab run.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

- `GLUE-020` infrastructure deployment completed.
- Systems Manager reports the EC2 instance as `Online`.
- The public repository exists at `/opt/aws-glue-postgres-mongodb-lab`.
- `git status --short` prints nothing.

**Inputs**

No user-supplied value is needed. The repository remote is already configured by the EC2 bootstrap.

**Command**

```bash
cd /opt/aws-glue-postgres-mongodb-lab
git fetch origin
git switch main
git merge --ff-only origin/main
git rev-parse HEAD | tee .lab-commit-sha
```

**Expected result**

The merge is already current or fast-forwards without conflict. The final command prints one 40-character Git SHA and writes the same SHA to `.lab-commit-sha`.

**Verify**

```bash
test "$(cat .lab-commit-sha)" = "$(git rev-parse HEAD)"
git status --short
```

Pass: the first command exits `0` and the second prints nothing; `.lab-commit-sha` is gitignored.

**Repeat, reset, or rollback**

Safe to repeat while the working tree is clean. Do not reset or discard local changes; stop if `git status --short` lists anything other than the local SHA record.

**If it fails**

- Symptom: `fatal: Not possible to fast-forward`.
- Cause: local `main` diverged from reviewed GitHub `main`.
- Diagnose: run `git log --oneline --decorate --graph --all -10`.
- Correct: preserve the output and stop; do not force-reset the lab checkout.
- Retry: after the branch discrepancy is resolved, repeat this step.

**Next**

Continue to Step 2 to create the local runtime environment without displaying secrets.

### Step 2 — Build the protected Compose environment from Secrets Manager

**Purpose**

Retrieve the two lab secret values with the EC2 instance role and write the exact environment contract required by Compose. Secret values are written only to a mode-`0600` local file and are never printed.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

- Step 1 passed.
- The EC2 instance role can read these secret containers:
  - `/aws-glue-postgres-mongodb-lab/postgres`
  - `/aws-glue-postgres-mongodb-lab/mongodb`
- The PostgreSQL secret JSON contains `username`, `password`, and `database`.
- The MongoDB secret JSON contains `root_username`, `root_password`, `username`, `password`, and `database`.
- `AWS_REGION` is `us-east-1`.

**Inputs**

```bash
export AWS_REGION="us-east-1"
export DATABASE_BIND_ADDRESS="$(hostname -I | cut -d' ' -f1)"
```

`DATABASE_BIND_ADDRESS` must resolve to the EC2 private IPv4 address, not a public address.

**Command**

Run the complete block as one action:

```bash
set -euo pipefail
umask 077
aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id /aws-glue-postgres-mongodb-lab/postgres \
  --query SecretString \
  --output text > /tmp/glue-lab-postgres.json
aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id /aws-glue-postgres-mongodb-lab/mongodb \
  --query SecretString \
  --output text > /tmp/glue-lab-mongodb.json
python3 - <<'PY'
import json
import os
from pathlib import Path

postgres = json.loads(Path("/tmp/glue-lab-postgres.json").read_text())
mongodb = json.loads(Path("/tmp/glue-lab-mongodb.json").read_text())
required_postgres = {"username", "password", "database"}
required_mongodb = {
    "root_username",
    "root_password",
    "username",
    "password",
    "database",
}
if not required_postgres <= postgres.keys() or not required_mongodb <= mongodb.keys():
    raise SystemExit("secret JSON is missing required keys")
lines = {
    "DATABASE_BIND_ADDRESS": os.environ["DATABASE_BIND_ADDRESS"],
    "POSTGRES_DB": postgres["database"],
    "POSTGRES_USER": postgres["username"],
    "POSTGRES_PASSWORD": postgres["password"],
    "MONGO_INITDB_ROOT_USERNAME": mongodb["root_username"],
    "MONGO_INITDB_ROOT_PASSWORD": mongodb["root_password"],
    "MONGO_DATABASE": mongodb["database"],
    "MONGO_GLUE_USERNAME": mongodb["username"],
    "MONGO_GLUE_PASSWORD": mongodb["password"],
}
if any(not str(value) for value in lines.values()):
    raise SystemExit("secret JSON contains an empty required value")
Path(".env").write_text("".join(f"{key}={value}\n" for key, value in lines.items()))
PY
chmod 600 .env
rm -f /tmp/glue-lab-postgres.json /tmp/glue-lab-mongodb.json
```

**Expected result**

The block exits `0`, prints no secret value, creates `.env` with mode `0600`, and removes both temporary JSON files.

**Verify**

```bash
python3 - <<'PY'
from pathlib import Path

path = Path(".env")
required = {
    "DATABASE_BIND_ADDRESS",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "MONGO_INITDB_ROOT_USERNAME",
    "MONGO_INITDB_ROOT_PASSWORD",
    "MONGO_DATABASE",
    "MONGO_GLUE_USERNAME",
    "MONGO_GLUE_PASSWORD",
}
values = dict(line.split("=", 1) for line in path.read_text().splitlines())
assert required == values.keys()
assert all(values.values())
assert path.stat().st_mode & 0o777 == 0o600
print("database environment: PASS")
PY
```

Pass: the command prints only `database environment: PASS`.

**Repeat, reset, or rollback**

Safe to repeat because the command replaces `.env`, but replacing `.env` does not change credentials already stored in initialized named volumes. After secret rotation, use `make ec2-reset-data` from the Mac rather than plain `make ec2-bootstrap`. Keep `.env` only through the immediately following Compose operation, then remove it as shown in Step 4. Temporary secret files must not survive the database operation.

**If it fails**

- Symptom: `AccessDeniedException` or `ResourceNotFoundException`.
- Cause: the EC2 role lacks access, the secret was not seeded, or the Region is wrong.
- Diagnose without reading values:

  ```bash
  aws secretsmanager describe-secret \
    --region "$AWS_REGION" \
    --secret-id /aws-glue-postgres-mongodb-lab/postgres
  ```

- Correct: complete the `GLUE-020` secret-seeding step or correct the instance-role permission.
- Retry: remove the two `/tmp/glue-lab-*.json` files and repeat Step 2.

**Next**

Continue to Step 3 to validate and start both databases.

### Step 3 — Start PostgreSQL and MongoDB

**Purpose**

Validate the Compose model, pull the pinned multi-architecture images, initialize both databases, and wait for health checks.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

- Step 2 passed.
- `docker version` succeeds.
- `docker compose version` succeeds.
- Ports `5432` and `27017` are not already in use on the EC2 private address.

**Inputs**

The mode-`0600` `.env` from Step 2 is the only input.

**Command**

```bash
make compose-check
make local-up
```

**Expected result**

Compose validation exits `0`. Docker pulls PostgreSQL `16.15-bookworm` and MongoDB `8.0.29-noble` on first use, creates only the project network and two named volumes, and reports both services healthy within 180 seconds.

**Verify**

```bash
make local-status
```

Pass: both `postgres` and `mongodb` are listed with state `running` and health `healthy`.

**Repeat, reset, or rollback**

Safe to repeat. Existing healthy containers remain running and named-volume data is retained. Run `make local-down` to stop only this Compose project without deleting data.

**If it fails**

- Image-pull failure: run `docker compose --env-file .env -f docker/compose.yaml pull` and inspect the exact registry error.
- Port conflict: run `docker ps --format '{{.Names}} {{.Ports}}'`; stop only the identified conflicting disposable container, then retry.
- Permission failure: run `docker version`; correct Docker access rather than adding public ports or changing the architecture.
- Unhealthy service: run `docker compose --env-file .env -f docker/compose.yaml logs --tail=100 postgres mongodb`; do not paste secret-bearing environment output.
- Retry: rerun `make local-up` after correcting the focused issue.

**Next**

Continue to Step 4 to prove the deterministic source and empty target state.

### Step 4 — Run source, failure-path, and target assertions

**Purpose**

Prove deterministic PostgreSQL counts and constraints, verify each isolated invalid fixture is rejected, rerun the seed safely, and confirm that the authenticated MongoDB target collection is initially empty.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

- Step 3 reports both services healthy.
- `.env` still has mode `0600`.

**Inputs**

No new input is required.

**Command**

```bash
make local-test
make local-test
rm -f .env
```

**Expected result**

Both test runs preserve the deterministic counts: 5 total orders, 4 active orders, 9 total items, and 7 active items belonging to active orders. Four invalid fixtures are rejected. MongoDB authenticates as the lab writer and reports zero order documents. The final line of each run is `local data assertions: PASS`; the temporary `.env` is then deleted immediately.

**Verify**

```bash
test ! -e .env
docker ps --filter label=com.docker.compose.project=aws-glue-postgres-mongodb-lab   --format '{{.Names}} {{.Status}}'
```

Pass: `.env` is absent and both project containers remain healthy.

**Repeat, reset, or rollback**

Safe to repeat. Valid fixtures use deterministic keys and upserts. Invalid fixtures run in isolated transactions and cannot leave rows behind.

**If it fails**

- Source assertion failure: inspect only `docker/postgres/init/01-schema.sql`, `02-seed.sql`, and `03-assert-valid.sql`; do not weaken the assertion.
- Invalid fixture unexpectedly succeeds: stop and restore the missing PostgreSQL constraint.
- MongoDB authentication failure: confirm the named volume was initialized with the current `.env`. If credentials changed after first initialization, use the controlled reset in Step 6.
- Retry: rerun `make local-test` after the focused correction.

**Next**

Continue to Step 5 to verify restart behavior, or Step 6 when a complete reseed is required.

### Step 5 — Verify a non-destructive restart

**Purpose**

Prove that stopping and starting the Compose project preserves named-volume data and deterministic checks.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

Step 4 passed.

**Inputs**

Repeat Step 2 to create a fresh mode-`0600` `.env` from Secrets Manager for this operation only.

**Command**

```bash
make local-down
make local-up
make local-test
rm -f .env
```

**Expected result**

Only the project containers stop and restart. The two named volumes remain. Both containers return to healthy state, and all assertions pass with unchanged counts.

**Verify**

```bash
make local-status
```

Pass: both services are healthy after the restart.

**Repeat, reset, or rollback**

Safe to repeat. This path never removes volumes.

**If it fails**

Run `docker compose --env-file .env -f docker/compose.yaml logs --tail=100 postgres mongodb`, correct the failing service, and repeat the complete command block.

**Next**

Use Step 6 only when intentionally rebuilding both disposable databases from their committed initializers.

### Step 6 — Reset and deterministically reseed the disposable data layer

**Purpose**

Remove only this project’s containers and named volumes, then rebuild from the committed schema and fixtures.

**Run from**

`EC2 through Systems Manager Session Manager — /opt/aws-glue-postgres-mongodb-lab`

**Prerequisites**

- You intend to delete all disposable PostgreSQL and MongoDB data in this lab project.
- Repeat Step 2 to create a fresh mode-`0600` `.env` for this operation only.
- `docker compose --env-file .env -f docker/compose.yaml config --format json` reports project name `aws-glue-postgres-mongodb-lab`.

**Inputs**

Set the explicit reset flag only for this command:

```bash
export RESET_VOLUMES=1
```

**Command**

```bash
make local-down RESET_VOLUMES=1
make local-up
make local-test
rm -f .env
```

**Expected result**

Compose removes only the fixed project’s containers, network, and two named volumes. Startup recreates the schema and deterministic fixtures, and all assertions pass.

**Verify**

```bash
make local-status
```

Pass: both newly created services are healthy.

**Repeat, reset, or rollback**

Repeating the block always returns the disposable data layer to the committed baseline. There is no recovery for data intentionally removed from these lab volumes; source fixtures are restored from Git.

**If it fails**

Run `docker compose --env-file .env -f docker/compose.yaml ps -a` and the focused service logs. Correct the initializer or credential mismatch, then repeat the full reset block. From the Mac, the supported SSM equivalent is `make ec2-reset-data`; it resolves the exact instance from Terraform state and performs this same fixed-project reset without printing current secrets.

**Next**

Proceed to [03 — Configure and Verify AWS Glue](03-CONFIGURE-GLUE.md).

## Optional — Run the data layer on the Mac

This path is a developer smoke test, not the core lab. Docker Desktop must be installed and running. It binds both database ports to loopback by default and uses generated disposable local credentials.

### Step M1 — Generate local credentials and run the same checks

**Purpose**

Exercise the exact Compose data layer locally without AWS resources.

**Run from**

`Mac Mini terminal — repository root`

**Prerequisites**

- `docker version` and `docker compose version` succeed.
- Ports `5432` and `27017` are free on `127.0.0.1`.
- The repository branch contains the reviewed GLUE-010 files.

**Inputs**

No secret value is supplied manually. Python generates three disposable random values.

**Command**

```bash
cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
values = []
for line in path.read_text().splitlines():
    key, separator, value = line.partition("=")
    if key in {
        "POSTGRES_PASSWORD",
        "MONGO_INITDB_ROOT_PASSWORD",
        "MONGO_GLUE_PASSWORD",
    }:
        value = secrets.token_hex(24)
    values.append(f"{key}{separator}{value}")
path.write_text("\n".join(values) + "\n")
PY
chmod 600 .env
make compose-check
make local-up
make local-test
```

**Expected result**

Both containers become healthy and the final command prints `local data assertions: PASS`.

**Verify**

```bash
make local-status
```

Pass: PostgreSQL and MongoDB are both healthy and their published addresses begin with `127.0.0.1`.

**Repeat, reset, or rollback**

Run `make local-down` to retain data, or `make local-down RESET_VOLUMES=1` to remove only the project volumes. Remove local credentials with `rm -f .env` after the smoke test.

**If it fails**

Use the focused image-pull, port, health, and initialization diagnostics from Step 3. On Apple Silicon, do not add a forced `platform`; both pinned images publish native `linux/arm64` and `linux/amd64` manifests.

**Next**

Return to the core sequence and proceed to [03 — Configure and Verify AWS Glue](03-CONFIGURE-GLUE.md).
