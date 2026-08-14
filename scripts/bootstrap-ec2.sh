#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="/opt/$project_name"
aws_cli="${AWS_CLI:-aws}"
aws_region="${AWS_REGION:-us-east-1}"
reset_data="${RESET_DATA:-0}"

if [[ "$reset_data" != "0" && "$reset_data" != "1" ]]; then
  printf 'ERROR: RESET_DATA must be 0 or 1.\n' >&2
  exit 1
fi

if [[ "$(id -un)" != "ec2-user" ]]; then
  printf 'ERROR: run this script as ec2-user through SSM.\n' >&2
  exit 1
fi
for command_name in "$aws_cli" docker git make python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'ERROR: required EC2 command is unavailable: %s\n' "$command_name" >&2
    exit 1
  fi
done

cd "$repo_root"
git pull --ff-only

tmp_dir="$(mktemp -d)"
env_file="$repo_root/.env"
trap 'rm -rf "$tmp_dir"; rm -f "$env_file"' EXIT
umask 077

"$aws_cli" --region "$aws_region" secretsmanager get-secret-value \
  --secret-id "/$project_name/postgres" --query SecretString --output text \
  >"$tmp_dir/postgres.json"
"$aws_cli" --region "$aws_region" secretsmanager get-secret-value \
  --secret-id "/$project_name/mongodb" --query SecretString --output text \
  >"$tmp_dir/mongodb.json"
"$aws_cli" --region "$aws_region" secretsmanager get-secret-value \
  --secret-id "/$project_name/mongodb-glue" --query SecretString --output text \
  >"$tmp_dir/mongodb-glue.json"

python3 - "$tmp_dir/postgres.json" "$tmp_dir/mongodb.json" "$tmp_dir/mongodb-glue.json" "$env_file" <<'PY'
import json
import pathlib
import sys

postgres = json.loads(pathlib.Path(sys.argv[1]).read_text())
mongodb = json.loads(pathlib.Path(sys.argv[2]).read_text())
mongodb_glue = json.loads(pathlib.Path(sys.argv[3]).read_text())
expected_postgres = {"host", "port", "database", "username", "password"}
expected_mongodb = {"host", "port", "database", "root_username", "root_password"}
expected_mongodb_glue = {"host", "port", "database", "username", "password"}
for name, payload, expected in (
    ("PostgreSQL", postgres, expected_postgres),
    ("MongoDB bootstrap", mongodb, expected_mongodb),
    ("MongoDB connector", mongodb_glue, expected_mongodb_glue),
):
    if set(payload) != expected or any(value in (None, "") for value in payload.values()):
        raise SystemExit(f"ERROR: {name} secret schema is invalid.")
if (
    mongodb["host"] != mongodb_glue["host"]
    or mongodb["port"] != mongodb_glue["port"]
    or mongodb["database"] != mongodb_glue["database"]
):
    raise SystemExit("ERROR: MongoDB bootstrap and connector secrets target different databases.")
values = {
    "AWS_REGION": "us-east-1",
    "DATABASE_BIND_ADDRESS": "0.0.0.0",
    "POSTGRES_DB": postgres["database"],
    "POSTGRES_USER": postgres["username"],
    "POSTGRES_PASSWORD": postgres["password"],
    "MONGO_INITDB_ROOT_USERNAME": mongodb["root_username"],
    "MONGO_INITDB_ROOT_PASSWORD": mongodb["root_password"],
    "MONGO_DATABASE": mongodb_glue["database"],
    "MONGO_GLUE_USERNAME": mongodb_glue["username"],
    "MONGO_GLUE_PASSWORD": mongodb_glue["password"],
}
path = pathlib.Path(sys.argv[4])
path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
path.chmod(0o600)
PY

if [[ "$reset_data" == "1" ]]; then
  compose_contract="$tmp_dir/compose-contract.json"
  docker compose --env-file "$env_file" -f docker/compose.yaml config --format json \
    >"$compose_contract"
  python3 - "$compose_contract" <<'PY'
import json
import pathlib
import sys

compose = json.loads(pathlib.Path(sys.argv[1]).read_text())
expected_project = "aws-glue-postgres-mongodb-lab"
expected_services = {"postgres", "mongodb"}
expected_volumes = {"postgres_data", "mongodb_data"}
if compose.get("name") != expected_project:
    raise SystemExit("ERROR: Compose project identity does not match the fixed lab project.")
if set(compose.get("services", {})) != expected_services:
    raise SystemExit("ERROR: Compose services do not match the two fixed lab databases.")
if set(compose.get("volumes", {})) != expected_volumes:
    raise SystemExit("ERROR: Compose volumes do not match the two fixed lab volumes.")
print("fixed Compose reset scope: PASS")
PY
  make local-down RESET_VOLUMES=1
fi

make local-up
make local-test
rm -f "$env_file"
git rev-parse HEAD >.lab-commit-sha
printf 'git_sha=%s\n' "$(<.lab-commit-sha)"
test ! -e "$env_file"
printf 'temporary environment cleanup: PASS\n'
printf 'aws-glue-postgres-mongodb-lab EC2 bootstrap: PASS\n'
