#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/user-run-aws-guard.sh"
require_user_run_aws APPROVE_GLUE_RUN
aws_cli="$USER_RUN_AWS_CLI"
terraform_bin="$USER_RUN_TERRAFORM"
timeout_seconds="${JOB_TIMEOUT_SECONDS:-1200}"
poll_seconds="${JOB_POLL_SECONDS:-15}"

[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || {
  printf '%s\n' 'ERROR: JOB_TIMEOUT_SECONDS must be a positive integer.' >&2
  exit 2
}
((timeout_seconds <= 3600)) || {
  printf '%s\n' 'ERROR: JOB_TIMEOUT_SECONDS maximum is 3600.' >&2
  exit 2
}
[[ "$poll_seconds" =~ ^[1-9][0-9]*$ ]] || {
  printf '%s\n' 'ERROR: JOB_POLL_SECONDS must be a positive integer.' >&2
  exit 2
}
((poll_seconds <= 60)) || {
  printf '%s\n' 'ERROR: JOB_POLL_SECONDS maximum is 60.' >&2
  exit 2
}

tf_root="$USER_RUN_TF_ROOT"
job_name="$($terraform_bin -chdir="$tf_root" output -raw glue_job_name)"
bucket="$($terraform_bin -chdir="$tf_root" output -raw artifact_bucket_name)"
local_sha="$(git -C "$USER_RUN_REPO_ROOT" rev-parse HEAD)"
if ! deployed_sha="$($aws_cli s3 cp "s3://$bucket/glue/artifacts/GIT_SHA" - \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --only-show-errors 2>/dev/null)"; then
  printf '%s\n' 'ERROR: deployed artifact revision marker is missing or unreadable.' >&2
  exit 1
fi
if [[ ! "$deployed_sha" =~ ^[0-9a-f]{40}$ || "$deployed_sha" != "$local_sha" ]]; then
  printf '%s\n' 'ERROR: deployed artifact revision does not match the clean local checkout.' >&2
  exit 1
fi
unset deployed_sha local_sha

job_run_id="$($aws_cli glue start-job-run --job-name "$job_name" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query JobRunId --output text)"
[[ -n "$job_run_id" && "$job_run_id" != "None" ]] || {
  printf '%s\n' 'ERROR: Glue did not return a job run identifier.' >&2
  exit 1
}

deadline_epoch=$(($(date +%s) + timeout_seconds))
while :; do
  state="$($aws_cli glue get-job-run --job-name "$job_name" --run-id "$job_run_id" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query 'JobRun.JobRunState' --output text)"
  case "$state" in
    SUCCEEDED)
      printf '%s\n' 'run: PASS (Glue job succeeded; identifiers redacted)'
      exit 0
      ;;
    FAILED|ERROR|TIMEOUT|STOPPED|EXPIRED)
      printf '%s\n' "ERROR: Glue job ended in $state." >&2
      printf '%s\n' 'Logs: aws logs tail /aws-glue/jobs/error --since 1h --follow' >&2
      exit 1
      ;;
    STARTING|RUNNING|STOPPING|WAITING)
      ;;
    *)
      printf '%s\n' 'ERROR: Glue job returned an unexpected redacted state.' >&2
      printf '%s\n' 'Logs: aws logs tail /aws-glue/jobs/error --since 1h --follow' >&2
      exit 1
      ;;
  esac
  now_epoch="$(date +%s)"
  remaining_seconds=$((deadline_epoch - now_epoch))
  ((remaining_seconds > 0)) || {
    printf '%s\n' "ERROR: Glue job did not finish within ${timeout_seconds}s." >&2
    printf '%s\n' 'Logs: aws logs tail /aws-glue/jobs/error --since 1h --follow' >&2
    exit 1
  }
  sleep_seconds="$poll_seconds"
  ((sleep_seconds <= remaining_seconds)) || sleep_seconds="$remaining_seconds"
  sleep "$sleep_seconds"
done
