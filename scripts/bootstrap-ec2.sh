#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="/opt/$project_name"
aws_cli="${AWS_CLI:-aws}"
aws_region="${AWS_REGION:-us-east-1}"

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
  > "$tmp_dir/postgres.json"
"$aws_cli" --region "$aws_region" secretsmanager get-secret-value \
  --secret-id "/$project_name/mongodb" --query SecretString --output text \
  > "$tmp_dir/mongodb.json"

python3 - "$tmp_dir/postgres.json" "$tmp_dir/mongodb.json" "$env_file" <<'PY'
import json
import pathlib
import sys
postgres = json.loads(pathlib.Path(sys.argv[1]).read_text())
mongodb = json.loads(pathlib.Path(sys.argv[2]).read_text())
values = {
    "AWS_REGION": "us-east-1",
    "DATABASE_BIND_ADDRESS": "0.0.0.0",
    "POSTGRES_DB": postgres["database"],
    "POSTGRES_USER": postgres["username"],
    "POSTGRES_PASSWORD": postgres["password"],
    "MONGO_INITDB_ROOT_USERNAME": mongodb["root_username"],
    "MONGO_INITDB_ROOT_PASSWORD": mongodb["root_password"],
    "MONGO_DATABASE": mongodb["database"],
    "MONGO_GLUE_USERNAME": mongodb["username"],
    "MONGO_GLUE_PASSWORD": mongodb["password"],
}
path = pathlib.Path(sys.argv[3])
path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
path.chmod(0o600)
PY

make local-up
make local-test
rm -f "$env_file"
git rev-parse HEAD > .lab-commit-sha
printf 'git_sha=%s\n' "$(<.lab-commit-sha)"
test ! -e "$env_file"
printf 'temporary environment cleanup: PASS\n'
printf 'aws-glue-postgres-mongodb-lab EC2 bootstrap: PASS\n'
