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
    AWS_ENDPOINT_URL|AWS_ENDPOINT_URL_*)
      printf '%s\n' 'ERROR: unset every AWS endpoint override before using the approved AWS_PROFILE.' >&2
      exit 1
      ;;
    TF_WORKSPACE|TF_DATA_DIR|TF_CLI_ARGS|TF_CLI_ARGS_*)
      if [[ -n "${!variable_name:-}" ]]; then
        printf 'ERROR: unset ambient AWS or Terraform override variables before using the approved AWS_PROFILE.\n' >&2
        exit 1
      fi
      ;;
  esac
done < <(compgen -e)
export AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true
export AWS_EC2_METADATA_DISABLED=true

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
if [[ -n "$(git -C "$repo_root" status --short)" ]]; then
  printf 'ERROR: commit or revert repository changes before creating a reviewed destroy plan.\n' >&2
  exit 1
fi
workspace="$($terraform_bin -chdir="$tf_root" workspace show)"
if [[ "$workspace" != "default" ]]; then
  printf 'ERROR: Terraform workspace must be default for the exact local state.\n' >&2
  exit 1
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
umask 077
rm -f "$metadata_file" "$plan_file"

"$terraform_bin" -chdir="$tf_root" state pull > "$work_dir/state.json"
"$terraform_bin" -chdir="$tf_root" state list | LC_ALL=C sort > "$work_dir/state-resources.txt"
python3 - "$work_dir/state.json" "$work_dir/state-resources.txt" "$state_file" \
  "$project_name" "$tf_root" <<'PY'
import json
import pathlib
import sys

state_path, resources_path, local_state_path, project, tf_root = sys.argv[1:]
state = json.loads(pathlib.Path(state_path).read_text())
local_state = json.loads(pathlib.Path(local_state_path).read_text())
resources = [line for line in pathlib.Path(resources_path).read_text().splitlines() if line]
outputs = state.get("outputs", {})
terraform_config = pathlib.Path(tf_root, "main.tf").read_text()
checks = [
    (f'project_name = "{project}"' in terraform_config, "Terraform configuration is not the fixed project"),
    (state.get("lineage"), "Terraform state lineage is missing"),
    (isinstance(state.get("serial"), int), "Terraform state serial is invalid"),
    (state.get("lineage") == local_state.get("lineage"), "active state lineage does not match terraform.tfstate"),
    (state.get("serial") == local_state.get("serial"), "active state serial does not match terraform.tfstate"),
    (resources, "Terraform state has no managed foundation resources"),
    (outputs.get("aws_region", {}).get("value") == "us-east-1", "Terraform state Region is not us-east-1"),
    (bool(outputs.get("aws_account_id", {}).get("value")), "Terraform state account output is missing"),
]
for passed, message in checks:
    if not passed:
        raise SystemExit(f"ERROR: {message}.")
print("project and Terraform state identity: PASS")
PY

"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$work_dir/identity.json"
python3 - "$work_dir/identity.json" "$work_dir/state.json" <<'PY'
import json
import pathlib
import sys
identity = json.loads(pathlib.Path(sys.argv[1]).read_text())
state = json.loads(pathlib.Path(sys.argv[2]).read_text())
state_account = state["outputs"]["aws_account_id"]["value"]
state_region = state["outputs"]["aws_region"]["value"]
if identity["Account"] != state_account:
    raise SystemExit("ERROR: current AWS account does not match Terraform state.")
if state_region != "us-east-1":
    raise SystemExit("ERROR: current AWS Region does not match Terraform state.")
print("AWS and Terraform state identity: PASS")
PY

"$terraform_bin" -chdir="$tf_root" plan -destroy -input=false -out=destroy.tfplan
"$terraform_bin" -chdir="$tf_root" state pull > "$work_dir/state.json"
"$terraform_bin" -chdir="$tf_root" state list | LC_ALL=C sort > "$work_dir/state-resources.txt"

python3 - "$work_dir/identity.json" "$work_dir/state.json" "$work_dir/state-resources.txt" \
  "$state_file" "$metadata_file" "$plan_file" "$project_name" "$repo_root" "$tf_root" \
  "$AWS_PROFILE" "$aws_region" "$(git -C "$repo_root" rev-parse HEAD)" <<'PY'
import hashlib
import json
import os
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
if state.get("lineage") != local_state.get("lineage") or state.get("serial") != local_state.get("serial"):
    raise SystemExit("ERROR: active state does not match terraform.tfstate after planning.")
resources = pathlib.Path(resources_path).read_bytes()
metadata = {
    "operation": "destroy",
    "account_id": identity["Account"],
    "principal_arn": identity["Arn"],
    "profile": profile,
    "region": region,
    "git_sha": git_sha,
    "project": project,
    "repo_root": repo_root,
    "terraform_root": tf_root,
    "state_lineage": state["lineage"],
    "state_serial": state["serial"],
    "state_resources_sha256": hashlib.sha256(resources).hexdigest(),
    "plan_sha256": hashlib.sha256(pathlib.Path(plan_path).read_bytes()).hexdigest(),
}
path = pathlib.Path(metadata_path)
path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
os.chmod(path, 0o600)
PY

printf 'Saved destroy.tfplan and private identity metadata bound to the exact project, roots, state, account, profile, Region, Git SHA, and plan_sha256.\n'
