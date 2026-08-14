#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project_name="aws-glue-postgres-mongodb-lab"
tf_root="$repo_root/infrastructure/terraform"
plan_file="$tf_root/tfplan"
metadata_file="$tf_root/.tfplan.identity.json"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

if [[ "${APPROVE_LAB_APPLY:-0}" != "1" ]]; then
  printf 'ERROR: set APPROVE_LAB_APPLY=1 after reviewing tfplan.\n' >&2
  exit 1
fi
: "${AWS_PROFILE:?ERROR: AWS_PROFILE is required.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: AWS_REGION must be us-east-1.\n' >&2
  exit 1
fi
if [[ ! -f "$plan_file" || ! -f "$metadata_file" ]]; then
  printf 'ERROR: run make infra-plan first; both tfplan and its identity metadata are required.\n' >&2
  exit 1
fi
if [[ -n "$(git -C "$repo_root" status --short)" ]]; then
  printf 'ERROR: repository changes invalidate the reviewed plan.\n' >&2
  exit 1
fi

identity_file="$(mktemp)"
trap 'rm -f "$identity_file"' EXIT
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$identity_file"

python3 - "$identity_file" "$metadata_file" "$plan_file" "$AWS_PROFILE" "$aws_region" \
  "$(git -C "$repo_root" rev-parse HEAD)" <<'PY'
import hashlib
import json
import pathlib
import sys
identity_path, metadata_path, plan_path, profile, region, git_sha = sys.argv[1:]
identity = json.loads(pathlib.Path(identity_path).read_text())
metadata = json.loads(pathlib.Path(metadata_path).read_text())
checks = [
    (identity["Account"] == metadata.get("account_id"), "AWS account does not match the reviewed plan"),
    (profile == metadata.get("profile"), "AWS profile name does not match the reviewed plan"),
    (region == metadata.get("region"), "AWS Region does not match the reviewed plan"),
    (git_sha == metadata.get("git_sha"), "Git SHA does not match the reviewed plan"),
    (
        hashlib.sha256(pathlib.Path(plan_path).read_bytes()).hexdigest()
        == metadata.get("plan_sha256"),
        "plan_sha256 does not match the reviewed plan",
    ),
]
for passed, message in checks:
    if not passed:
        raise SystemExit(f"ERROR: {message}.")
print("reviewed plan identity: PASS")
PY

"$terraform_bin" -chdir="$tf_root" apply -input=false tfplan
rm -f "$metadata_file" "$plan_file"
printf '%s reviewed plan apply: PASS\n' "$project_name"
