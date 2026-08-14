#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib/user-run-aws-guard.sh"
require_user_run_aws "APPROVE_LAB_SECRETS"

tf_root="$USER_RUN_TF_ROOT"
terraform_bin="$USER_RUN_TERRAFORM"
aws_cli="$USER_RUN_AWS_CLI"
aws_region="$AWS_REGION"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
umask 077

postgres_secret="$($terraform_bin -chdir="$tf_root" output -raw postgres_secret_name)"
mongodb_secret="$($terraform_bin -chdir="$tf_root" output -raw mongodb_secret_name)"
mongodb_glue_secret="$($terraform_bin -chdir="$tf_root" output -raw mongodb_glue_secret_name)"
database_host="$($terraform_bin -chdir="$tf_root" output -raw database_private_ip)"

postgres_path="$tmp_dir/postgres.json"
mongodb_path="$tmp_dir/mongodb.json"
mongodb_glue_path="$tmp_dir/mongodb-glue.json"
python3 - "$postgres_path" "$mongodb_path" "$mongodb_glue_path" "$database_host" <<'PY'
import json
import pathlib
import secrets
import sys

postgres_path, mongodb_path, mongodb_glue_path, host = sys.argv[1:]
pathlib.Path(postgres_path).write_text(json.dumps({
    "host": host,
    "port": 5432,
    "database": "sales_lab",
    "username": "lab_admin",
    "password": secrets.token_hex(24),
}))
pathlib.Path(mongodb_path).write_text(json.dumps({
    "host": host,
    "port": 27017,
    "database": "migration_lab",
    "root_username": "lab_root",
    "root_password": secrets.token_hex(24),
}))
pathlib.Path(mongodb_glue_path).write_text(json.dumps({
    "host": host,
    "port": 27017,
    "database": "migration_lab",
    "username": "glue_writer",
    "password": secrets.token_hex(24),
}))
PY

"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" secretsmanager put-secret-value \
  --secret-id "$postgres_secret" --secret-string "file://$postgres_path" >/dev/null
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" secretsmanager put-secret-value \
  --secret-id "$mongodb_secret" --secret-string "file://$mongodb_path" >/dev/null
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" secretsmanager put-secret-value \
  --secret-id "$mongodb_glue_secret" --secret-string "file://$mongodb_glue_path" >/dev/null

printf 'Stored fresh generated values in the three %s secret containers.\n' \
  'aws-glue-postgres-mongodb-lab'
printf 'No secret value was printed.\n'
printf 'If databases already use named volumes, run make ec2-reset-data; make ec2-bootstrap alone does not rotate initialized database credentials.\n'
