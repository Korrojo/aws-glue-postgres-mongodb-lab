#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tf_root="$repo_root/infrastructure/terraform"
state_file="$tf_root/terraform.tfstate"
plan_file="$tf_root/destroy.tfplan"
metadata_file="$tf_root/.destroy.tfplan.identity.json"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

ambient_credential_vars=(
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN
  AWS_SECURITY_TOKEN
  AWS_WEB_IDENTITY_TOKEN_FILE
  AWS_ROLE_ARN
  AWS_ROLE_SESSION_NAME
  AWS_CONTAINER_CREDENTIALS_RELATIVE_URI
  AWS_CONTAINER_CREDENTIALS_FULL_URI
  AWS_CONTAINER_AUTHORIZATION_TOKEN
  AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
)
for variable_name in "${ambient_credential_vars[@]}"; do
  if [[ -n "${!variable_name:-}" ]]; then
    printf 'ERROR: unset ambient AWS or Terraform override variables before using the approved AWS_PROFILE.\n' >&2
    exit 1
  fi
done
while IFS= read -r variable_name; do
  case "$variable_name" in
    TF_WORKSPACE|TF_DATA_DIR|TF_CLI_ARGS|TF_CLI_ARGS_*)
      if [[ -n "${!variable_name:-}" ]]; then
        printf 'ERROR: unset ambient AWS or Terraform override variables before using the approved AWS_PROFILE.\n' >&2
        exit 1
      fi
      ;;
  esac
done < <(compgen -e)
export AWS_EC2_METADATA_DISABLED=true

if [[ "${APPROVE_LAB_DESTROY:-0}" != "1" ]]; then
  printf 'ERROR: set APPROVE_LAB_DESTROY=1 after reviewing destroy.tfplan.\n' >&2
  exit 1
fi
: "${AWS_PROFILE:?ERROR: AWS_PROFILE is required.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: AWS_REGION must be us-east-1.\n' >&2
  exit 1
fi
if [[ "$(basename "$repo_root")" != "$project_name" ]]; then
  printf 'ERROR: repository directory must be exactly %s.\n' "$project_name" >&2
  exit 1
fi
git_root="$(git -C "$repo_root" rev-parse --show-toplevel)"
if [[ "$(cd "$git_root" && pwd -P)" != "$repo_root" ]]; then
  printf 'ERROR: script did not resolve the exact repository root.\n' >&2
  exit 1
fi
if [[ ! -d "$tf_root" || "$(cd "$tf_root" && pwd -P)" != "$repo_root/infrastructure/terraform" ]]; then
  printf 'ERROR: Terraform root identity does not match this project.\n' >&2
  exit 1
fi
if [[ ! -f "$state_file" || -L "$state_file" ]]; then
  printf 'ERROR: exact local Terraform state %s is required and must not be a symlink.\n' "$state_file" >&2
  exit 1
fi
if [[ ! -f "$plan_file" || -L "$plan_file" || ! -f "$metadata_file" || -L "$metadata_file" ]]; then
  printf 'ERROR: run make destroy-plan first; the reviewed plan and identity metadata are required.\n' >&2
  exit 1
fi
if [[ -n "$(git -C "$repo_root" status --short)" ]]; then
  printf 'ERROR: repository changes invalidate the reviewed destroy plan.\n' >&2
  exit 1
fi
workspace="$($terraform_bin -chdir="$tf_root" workspace show)"
if [[ "$workspace" != "default" ]]; then
  printf 'ERROR: Terraform workspace must be default for the exact local state.\n' >&2
  exit 1
fi

work_dir="$(mktemp -d)"
apply_attempted="0"
cleanup() {
  rm -rf "$work_dir"
  if [[ "$apply_attempted" == "1" ]]; then
    rm -f "$metadata_file" "$plan_file"
  fi
}
trap cleanup EXIT
umask 077
"$terraform_bin" -chdir="$tf_root" state pull > "$work_dir/state.json"
"$terraform_bin" -chdir="$tf_root" state list | LC_ALL=C sort > "$work_dir/state-resources.txt"
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$work_dir/identity.json"

python3 - "$work_dir/identity.json" "$work_dir/state.json" "$work_dir/state-resources.txt" \
  "$state_file" "$metadata_file" "$plan_file" "$project_name" "$repo_root" "$tf_root" \
  "$AWS_PROFILE" "$aws_region" "$(git -C "$repo_root" rev-parse HEAD)" <<'PY'
import hashlib
import json
import pathlib
import sys
(
    identity_path,
    state_path,
    resources_path,
    local_state_path,
    metadata_path,
    plan_path,
    project,
    repo_root,
    tf_root,
    profile,
    region,
    git_sha,
) = sys.argv[1:]
identity = json.loads(pathlib.Path(identity_path).read_text())
state = json.loads(pathlib.Path(state_path).read_text())
local_state = json.loads(pathlib.Path(local_state_path).read_text())
metadata = json.loads(pathlib.Path(metadata_path).read_text())
resources = pathlib.Path(resources_path).read_bytes()
outputs = state.get("outputs", {})
terraform_config = pathlib.Path(tf_root, "main.tf").read_text()
checks = [
    (metadata.get("operation") == "destroy", "operation is not destroy in the reviewed plan metadata"),
    (state.get("lineage") == local_state.get("lineage"), "active state lineage does not match terraform.tfstate"),
    (state.get("serial") == local_state.get("serial"), "active state serial does not match terraform.tfstate"),
    (metadata.get("project") == project, "project does not match the reviewed destroy plan"),
    (f'project_name = "{project}"' in terraform_config, "Terraform configuration is not the fixed project"),
    (metadata.get("repo_root") == repo_root, "repository root does not match the reviewed destroy plan"),
    (metadata.get("terraform_root") == tf_root, "Terraform root does not match the reviewed destroy plan"),
    (identity["Account"] == metadata.get("account_id"), "AWS account does not match the reviewed destroy plan"),
    (identity["Arn"] == metadata.get("principal_arn"), "AWS principal does not match the reviewed destroy plan"),
    (outputs.get("aws_account_id", {}).get("value") == identity["Account"], "Terraform state account does not match current AWS identity"),
    (profile == metadata.get("profile"), "AWS profile name does not match the reviewed destroy plan"),
    (region == metadata.get("region") == outputs.get("aws_region", {}).get("value"), "AWS Region does not match the reviewed destroy plan and state"),
    (git_sha == metadata.get("git_sha"), "Git SHA does not match the reviewed destroy plan"),
    (state.get("lineage") == metadata.get("state_lineage"), "state_lineage does not match the reviewed destroy plan"),
    (state.get("serial") == metadata.get("state_serial"), "state_serial does not match the reviewed destroy plan"),
    (hashlib.sha256(resources).hexdigest() == metadata.get("state_resources_sha256"), "state_resources_sha256 does not match the reviewed destroy plan"),
    (hashlib.sha256(pathlib.Path(plan_path).read_bytes()).hexdigest() == metadata.get("plan_sha256"), "plan_sha256 does not match the reviewed destroy plan"),
]
for passed, message in checks:
    if not passed:
        raise SystemExit(f"ERROR: {message}.")
print("reviewed destroy plan identity: PASS")
PY

apply_attempted="1"
"$terraform_bin" -chdir="$tf_root" apply -input=false destroy.tfplan
remaining="$($terraform_bin -chdir="$tf_root" state list)"
if [[ -n "$remaining" ]]; then
  printf 'ERROR: Terraform state still contains managed resources after destroy.\n' >&2
  exit 1
fi
printf '%s Terraform-managed foundation destroy verification: PASS\n' "$project_name"
printf 'destroy verification: PASS\n'
