#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/lib/user-run-aws-guard.sh"
source "$script_dir/lib/user-run-ssm.sh"
require_user_run_aws APPROVE_GLUE_RERUN

rerun_complete=0
cleanup_notice() {
  if [[ "$rerun_complete" != "1" ]]; then
    printf '%s\n' 'ERROR: rerun proof stopped. Use the reset block in runbook 05 before retrying.' >&2
  fi
}
trap cleanup_notice EXIT

remote_python='/opt/aws-glue-postgres-mongodb-lab/validation/rerun.py'
remote_reconcile='/opt/aws-glue-postgres-mongodb-lab/validation/reconcile.py'
summary='/var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json'
fingerprint='/var/tmp/aws-glue-postgres-mongodb-lab/rerun-fingerprint.json'

remote_action() {
  local action="$1"
  run_user_ssm_command "sudo -u ec2-user python3 $remote_python $action"
}
run_glue() {
  APPROVE_GLUE_RUN=1 AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    TERRAFORM="$USER_RUN_TERRAFORM" AWS_CLI="$USER_RUN_AWS_CLI" \
    "$script_dir/run-glue-job.sh"
}
validate_remote() {
  run_user_ssm_command \
    "sudo -u ec2-user python3 $remote_reconcile --output $summary"
}
fingerprint_remote() {
  run_user_ssm_command \
    "sudo -u ec2-user python3 $remote_python fingerprint --output $fingerprint"
}

printf '%s\n' 'phase=reset fixtures_to_known_baseline'
remote_action reset-update
remote_action restore-source
run_glue
validate_remote
baseline_fingerprint="$(fingerprint_remote)"

printf '%s\n' 'phase=unchanged_second_run'
run_glue
validate_remote
unchanged_fingerprint="$(fingerprint_remote)"
[[ "$unchanged_fingerprint" == "$baseline_fingerprint" ]] || {
  printf '%s\n' 'ERROR: unchanged second run changed redacted target count/hash.' >&2
  exit 1
}
printf '%s\n' 'unchanged_second_run: PASS'

printf '%s\n' 'phase=controlled_replacement'
remote_action apply-update
run_glue
validate_remote
updated_fingerprint="$(fingerprint_remote)"
[[ "$updated_fingerprint" != "$baseline_fingerprint" ]] || {
  printf '%s\n' 'ERROR: controlled replacement did not change redacted target hash.' >&2
  exit 1
}
printf '%s\n' 'controlled_replacement: PASS'

remote_action reset-update
run_glue
validate_remote

printf '%s\n' 'phase=stale_target_detection'
remote_action soft-delete
run_glue
stale_command="sudo -u ec2-user bash -c 'set +e; python3 $remote_reconcile --output $summary; rc=\$?; set -e; test \"\$rc\" -eq 1; python3 $remote_python assert-stale --summary $summary'"
run_user_ssm_command "$stale_command"
printf '%s\n' 'stale_target_detection: PASS'

printf '%s\n' 'phase=targeted_stale_resolution'
remote_action delete-stale-target
validate_remote
printf '%s\n' 'targeted_stale_resolution: PASS'

printf '%s\n' 'phase=reset'
remote_action restore-source
run_glue
validate_remote
reset_fingerprint="$(fingerprint_remote)"
[[ "$reset_fingerprint" == "$baseline_fingerprint" ]] || {
  printf '%s\n' 'ERROR: final reset did not restore the baseline redacted target hash.' >&2
  exit 1
}
printf '%s\n' 'reset: PASS'

rerun_complete=1
trap - EXIT
printf '%s\n' 'rerun-test: PASS (unchanged, replacement, stale detection/resolution, reset)'
