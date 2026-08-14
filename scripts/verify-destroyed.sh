#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tf_root="$repo_root/infrastructure/terraform"
state_file="$tf_root/terraform.tfstate"
aws_cli="${AWS_CLI:-aws}"
terraform_bin="${TERRAFORM:-terraform}"

[[ "${APPROVE_LAB_DESTROY_VERIFY:-0}" == "1" ]] || {
  printf '%s\n' 'ERROR: post-destroy verification requires the consumed-plan approval chain.' >&2
  exit 2
}
ambient=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN \
  AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_ROLE_SESSION_NAME \
  AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI \
  AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE)
for variable_name in "${ambient[@]}"; do
  [[ -z "${!variable_name:-}" ]] || {
    printf '%s\n' 'ERROR: unset ambient AWS or Terraform override variables.' >&2
    exit 2
  }
done
while IFS= read -r variable_name; do
  case "$variable_name" in
    AWS_ENDPOINT_URL|AWS_ENDPOINT_URL_*)
      printf '%s\n' 'ERROR: unset every AWS endpoint override.' >&2
      exit 2
      ;;
    TF_WORKSPACE|TF_DATA_DIR|TF_CLI_ARGS|TF_CLI_ARGS_*)
      [[ -z "${!variable_name:-}" ]] || {
        printf '%s\n' 'ERROR: unset ambient AWS or Terraform override variables.' >&2
        exit 2
      }
      ;;
  esac
done < <(compgen -e)
export AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true
export AWS_EC2_METADATA_DISABLED=true

: "${AWS_PROFILE:?ERROR: AWS_PROFILE is required.}"
[[ "${AWS_REGION:-}" == "us-east-1" ]] || {
  printf '%s\n' 'ERROR: AWS_REGION must be us-east-1.' >&2
  exit 2
}
: "${EXPECTED_AWS_ACCOUNT:?ERROR: exact destroy-bound account is required.}"
: "${EXPECTED_ARTIFACT_BUCKET:?ERROR: exact destroy-bound artifact bucket is required.}"
[[ "$(basename "$repo_root")" == "$project_name" ]] || {
  printf '%s\n' 'ERROR: unexpected repository root.' >&2
  exit 2
}
[[ "$(git -C "$repo_root" rev-parse --show-toplevel)" == "$repo_root" ]] || {
  printf '%s\n' 'ERROR: run from the exact cloned lab repository.' >&2
  exit 2
}
[[ -z "$(git -C "$repo_root" status --short)" ]] || {
  printf '%s\n' 'ERROR: repository must remain clean after reviewed-plan consumption.' >&2
  exit 2
}
[[ -f "$state_file" && ! -L "$state_file" ]] || {
  printf '%s\n' 'ERROR: exact local Terraform state is required.' >&2
  exit 2
}
[[ "$($terraform_bin -chdir="$tf_root" workspace show)" == "default" ]] || {
  printf '%s\n' 'ERROR: Terraform workspace must be default.' >&2
  exit 2
}
[[ -z "$($terraform_bin -chdir="$tf_root" state list)" ]] || {
  printf '%s\n' 'ERROR: Terraform state still contains managed resources.' >&2
  exit 1
}
current_account="$($aws_cli sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query Account --output text)"
[[ "$current_account" == "$EXPECTED_AWS_ACCOUNT" ]] || {
  printf '%s\n' 'ERROR: AWS account does not match the consumed destroy plan.' >&2
  exit 2
}
unset current_account

common=(--profile "$AWS_PROFILE" --region "$AWS_REGION" --output text)
project_filters=("Name=tag:Project,Values=$project_name" 'Name=tag:Environment,Values=lab' 'Name=tag:ManagedBy,Values=terraform')
tagged_count="$($aws_cli resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=$project_name" 'Key=Environment,Values=lab' 'Key=ManagedBy,Values=terraform' \
  "${common[@]}" --query 'length(ResourceTagMappingList)')"
instance_count="$($aws_cli ec2 describe-instances --filters "${project_filters[@]}" \
  'Name=instance-state-name,Values=pending,running,stopping,stopped' \
  "${common[@]}" --query 'length(Reservations[].Instances[])')"
endpoint_count="$($aws_cli ec2 describe-vpc-endpoints --filters "${project_filters[@]}" \
  "${common[@]}" --query 'length(VpcEndpoints)')"
bucket_count="$($aws_cli s3api list-buckets "${common[@]}" \
  --query "length(Buckets[?Name=='$EXPECTED_ARTIFACT_BUCKET'])")"

work_dir="$(mktemp -d)"
chmod 0700 "$work_dir"
trap 'rm -rf "$work_dir"' EXIT
umask 077
known_remainder=0
expect_service_absent() {
  local expected_error="$1"
  shift
  if "$@" >"$work_dir/service-output" 2>"$work_dir/service-error"; then
    known_remainder=$((known_remainder + 1))
    return
  fi
  local error_text
  error_text="$(<"$work_dir/service-error")"
  [[ "$error_text" == *"$expected_error"* ]] || {
    printf '%s\n' 'ERROR: a known-service absence check failed unexpectedly.' >&2
    exit 2
  }
}

expect_service_absent EntityNotFoundException \
  "$aws_cli" glue get-job --job-name "$project_name-orders-to-mongodb" "${common[@]}"
expect_service_absent EntityNotFoundException \
  "$aws_cli" glue get-crawler --name "$project_name-orders" "${common[@]}"
expect_service_absent EntityNotFoundException \
  "$aws_cli" glue get-connection --name "$project_name-postgres" "${common[@]}"
expect_service_absent EntityNotFoundException \
  "$aws_cli" glue get-connection --name "$project_name-mongodb" "${common[@]}"
expect_service_absent EntityNotFoundException \
  "$aws_cli" glue get-database --name aws_glue_postgres_mongodb_lab "${common[@]}"
for secret_name in postgres mongodb mongodb-glue; do
  expect_service_absent ResourceNotFoundException \
    "$aws_cli" secretsmanager describe-secret --secret-id "/$project_name/$secret_name" "${common[@]}"
done
for role_name in "$project_name-ec2" "$project_name-glue"; do
  expect_service_absent NoSuchEntity \
    "$aws_cli" iam get-role --role-name "$role_name" "${common[@]}"
done

python3 - "$tagged_count" "$instance_count" "$endpoint_count" "$bucket_count" "$known_remainder" <<'PY'
import json
import sys
names = ("project_tagged", "ec2_instances", "vpc_endpoints", "artifact_buckets", "known_named")
try:
    counts = dict(zip(names, map(int, sys.argv[1:]), strict=True))
except (TypeError, ValueError):
    raise SystemExit("ERROR: post-destroy inventory returned a nonnumeric result.")
print(json.dumps({"schema_version": 1, "counts": counts}, sort_keys=True, separators=(",", ":")))
if any(counts.values()):
    raise SystemExit("ERROR: known project resource remains after destroy; identifiers redacted.")
PY
printf '%s\n' 'post-destroy known-service verification: PASS'
