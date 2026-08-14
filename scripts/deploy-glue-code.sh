#!/usr/bin/env bash
set -euo pipefail

artifact_prefix="glue/artifacts"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/user-run-aws-guard.sh"
require_user_run_aws APPROVE_GLUE_DEPLOY

aws_cli="$USER_RUN_AWS_CLI"
terraform_bin="$USER_RUN_TERRAFORM"
repo_root="$USER_RUN_REPO_ROOT"
tf_root="$USER_RUN_TF_ROOT"
bucket="$($terraform_bin -chdir="$tf_root" output -raw artifact_bucket_name)"
git_sha="$(git -C "$repo_root" rev-parse HEAD)"
tmp_dir="$(mktemp -d)"
cleanup() { rm -rf "$tmp_dir"; }
trap cleanup EXIT

(
  cd "$repo_root/src"
  zip -q -r "$tmp_dir/glue_lab.zip" glue_lab -x '*/__pycache__/*' '*.pyc'
)
printf '%s\n' "$git_sha" >"$tmp_dir/GIT_SHA"

"$aws_cli" s3 cp "$repo_root/glue/jobs/postgres_orders_to_mongodb.py" \
  "s3://$bucket/$artifact_prefix/jobs/postgres_orders_to_mongodb.py" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --sse AES256 --only-show-errors
"$aws_cli" s3 cp "$tmp_dir/glue_lab.zip" \
  "s3://$bucket/$artifact_prefix/python/glue_lab.zip" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --sse AES256 --only-show-errors
"$aws_cli" s3 cp "$tmp_dir/GIT_SHA" "s3://$bucket/$artifact_prefix/GIT_SHA" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --sse AES256 --only-show-errors

printf '%s\n' "deploy: PASS (prefix $artifact_prefix; Git SHA recorded)"
