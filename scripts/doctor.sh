#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

required=(git make python3 "$terraform_bin" "$aws_cli")
for command_name in "${required[@]}"; do
  if ! command -v "$command_name" >/dev/null 2>&1 && [[ ! -x "$command_name" ]]; then
    printf 'ERROR: required command is unavailable: %s\n' "$command_name" >&2
    exit 1
  fi
done

: "${AWS_PROFILE:?Set AWS_PROFILE to a personal lab profile.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: set AWS_REGION=us-east-1 for this lab.\n' >&2
  exit 1
fi

if [[ ! -d "$repo_root/.git" ]]; then
  printf 'ERROR: run from the cloned aws-glue-postgres-mongodb-lab repository.\n' >&2
  exit 1
fi

identity_file="$(mktemp)"
trap 'rm -f "$identity_file"' EXIT
"$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" sts get-caller-identity \
  --output json > "$identity_file"

python3 - "$identity_file" <<'PY'
import json
import pathlib
import sys
identity = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(f"AWS account: {identity['Account']}")
print(f"AWS principal: {identity['Arn']}")
PY

printf 'AWS Region: %s\n' "$aws_region"
printf 'Git revision: %s\n' "$(git -C "$repo_root" rev-parse HEAD)"
"$terraform_bin" version
if command -v docker >/dev/null 2>&1; then
  docker version --format 'Docker client: {{.Client.Version}}' 2>/dev/null || true
else
  printf 'Docker: optional locally; not installed\n'
fi
printf 'doctor: PASS\n'
