#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tf_root="$repo_root/infrastructure/terraform"
plan_file="$tf_root/tfplan"
metadata_file="$tf_root/.tfplan.identity.json"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

: "${AWS_PROFILE:?ERROR: AWS_PROFILE is required.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: AWS_REGION must be us-east-1.\n' >&2
  exit 1
fi
if [[ -n "$(git -C "$repo_root" status --short)" ]]; then
  printf 'ERROR: commit or revert repository changes before creating a reviewed plan.\n' >&2
  exit 1
fi

identity_file="$(mktemp)"
trap 'rm -f "$identity_file"' EXIT
rm -f "$metadata_file"
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$identity_file"
"$terraform_bin" -chdir="$tf_root" plan -input=false -out=tfplan

python3 - "$identity_file" "$metadata_file" "$plan_file" "$AWS_PROFILE" "$aws_region" \
  "$(git -C "$repo_root" rev-parse HEAD)" <<'PY'
import hashlib
import json
import os
import pathlib
import sys
identity_path, metadata_path, plan_path, profile, region, git_sha = sys.argv[1:]
identity = json.loads(pathlib.Path(identity_path).read_text())
plan_sha256 = hashlib.sha256(pathlib.Path(plan_path).read_bytes()).hexdigest()
metadata = {
    "account_id": identity["Account"],
    "principal_arn": identity["Arn"],
    "profile": profile,
    "region": region,
    "git_sha": git_sha,
    "plan_sha256": plan_sha256,
}
path = pathlib.Path(metadata_path)
path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
os.chmod(path, 0o600)
PY

printf 'Saved tfplan and private identity metadata for the reviewed aws-glue-postgres-mongodb-lab account, Region, Git SHA, and plan_sha256.\n'
