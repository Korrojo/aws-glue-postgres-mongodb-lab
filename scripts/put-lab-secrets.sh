#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tf_root="$repo_root/infrastructure/terraform"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

: "${AWS_PROFILE:?Set AWS_PROFILE to a personal lab profile.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: set AWS_REGION=us-east-1 for this lab.\n' >&2
  exit 1
fi

for command_name in "$terraform_bin" "$aws_cli" python3; do
  if ! command -v "$command_name" >/dev/null 2>&1 && [[ ! -x "$command_name" ]]; then
    printf 'ERROR: required command is unavailable: %s\n' "$command_name" >&2
    exit 1
  fi
done

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
umask 077

"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$tmp_dir/identity.json"
current_account="$(python3 - "$tmp_dir/identity.json" <<'PY'
import json
import pathlib
import sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["Account"])
PY
)"
state_account="$($terraform_bin -chdir="$tf_root" output -raw aws_account_id)"
state_region="$($terraform_bin -chdir="$tf_root" output -raw aws_region)"
if [[ "$current_account" != "$state_account" ]]; then
  printf 'ERROR: current AWS account does not match Terraform state.\n' >&2
  exit 1
fi
if [[ "$aws_region" != "$state_region" ]]; then
  printf 'ERROR: current AWS Region does not match Terraform state.\n' >&2
  exit 1
fi

postgres_secret="$($terraform_bin -chdir="$tf_root" output -raw postgres_secret_name)"
mongodb_secret="$($terraform_bin -chdir="$tf_root" output -raw mongodb_secret_name)"
database_host="$($terraform_bin -chdir="$tf_root" output -raw database_private_ip)"

python3 - "$tmp_dir/postgres.json" "$tmp_dir/mongodb.json" "$database_host" <<'PY'
import json
import pathlib
import secrets
import sys
postgres_path, mongodb_path, host = sys.argv[1:]
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
    "username": "glue_writer",
    "password": secrets.token_hex(24),
}))
PY

"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" secretsmanager put-secret-value \
  --secret-id "$postgres_secret" --secret-string "file://$tmp_dir/postgres.json" >/dev/null
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" secretsmanager put-secret-value \
  --secret-id "$mongodb_secret" --secret-string "file://$tmp_dir/mongodb.json" >/dev/null

printf 'Stored fresh generated values in the two %s secret containers.\n' \
  'aws-glue-postgres-mongodb-lab'
printf 'No secret value was printed.\n'
