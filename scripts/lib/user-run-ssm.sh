#!/usr/bin/env bash
set -euo pipefail

run_user_ssm_command() (
  local remote_command="$1"
  local expected_git_sha
  expected_git_sha="$(git -C "$USER_RUN_REPO_ROOT" rev-parse HEAD)"
  [[ "$expected_git_sha" =~ ^[0-9a-f]{40}$ ]] || {
    printf '%s\n' 'ERROR: local reviewed Git SHA is invalid.' >&2
    return 2
  }
  remote_command="test -z \"\$(sudo -u ec2-user git -C /opt/aws-glue-postgres-mongodb-lab status --short)\" && test \"\$(sudo -u ec2-user git -C /opt/aws-glue-postgres-mongodb-lab rev-parse HEAD)\" = '$expected_git_sha' && $remote_command"
  local timeout_seconds="${SSM_TIMEOUT_SECONDS:-900}"
  local poll_seconds="${SSM_POLL_SECONDS:-10}"
  [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || {
    printf '%s\n' 'ERROR: SSM_TIMEOUT_SECONDS must be a positive integer.' >&2
    return 2
  }
  ((timeout_seconds <= 1800)) || {
    printf '%s\n' 'ERROR: SSM_TIMEOUT_SECONDS maximum is 1800.' >&2
    return 2
  }
  [[ "$poll_seconds" =~ ^[1-9][0-9]*$ ]] || {
    printf '%s\n' 'ERROR: SSM_POLL_SECONDS must be a positive integer.' >&2
    return 2
  }
  ((poll_seconds <= 60)) || {
    printf '%s\n' 'ERROR: SSM_POLL_SECONDS maximum is 60.' >&2
    return 2
  }

  local work_dir parameters_file output_file instance_id command_id state
  work_dir="$(mktemp -d)"
  parameters_file="$work_dir/parameters.json"
  output_file="$work_dir/output.txt"
  chmod 0700 "$work_dir"
  trap 'rm -rf "$work_dir"' EXIT
  umask 077
  python3 - "$parameters_file" "$remote_command" <<'PY'
import json
import os
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({"commands": [sys.argv[2]]}, separators=(",", ":")))
os.chmod(path, 0o600)
PY
  instance_id="$($USER_RUN_TERRAFORM -chdir="$USER_RUN_TF_ROOT" output -raw database_instance_id)"
  command_id="$($USER_RUN_AWS_CLI ssm send-command \
    --instance-ids "$instance_id" \
    --document-name AWS-RunShellScript \
    --timeout-seconds "$timeout_seconds" \
    --comment 'aws-glue-postgres-mongodb-lab bounded user-run operation' \
    --parameters "file://$parameters_file" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query 'Command.CommandId' --output text)"
  [[ -n "$command_id" && "$command_id" != "None" ]] || {
    printf '%s\n' 'ERROR: SSM did not return a command identifier.' >&2
    return 1
  }

  local deadline_epoch now_epoch remaining_seconds sleep_seconds
  deadline_epoch=$(($(date +%s) + timeout_seconds))
  state="Pending"
  while :; do
    state="$($USER_RUN_AWS_CLI ssm get-command-invocation \
      --command-id "$command_id" --instance-id "$instance_id" \
      --profile "$AWS_PROFILE" --region "$AWS_REGION" \
      --query Status --output text 2>/dev/null || true)"
    case "$state" in
      Success)
        break
        ;;
      Failed|Cancelled|Cancelling|TimedOut)
        printf '%s\n' 'ERROR: user-run SSM command failed; identifiers redacted.' >&2
        return 1
        ;;
      Pending|InProgress|Delayed|"")
        ;;
      *)
        printf '%s\n' 'ERROR: user-run SSM command returned an unexpected state.' >&2
        return 1
        ;;
    esac
    now_epoch="$(date +%s)"
    remaining_seconds=$((deadline_epoch - now_epoch))
    ((remaining_seconds > 0)) || {
      printf '%s\n' 'ERROR: user-run SSM command exceeded its bounded deadline.' >&2
      return 1
    }
    sleep_seconds="$poll_seconds"
    ((sleep_seconds <= remaining_seconds)) || sleep_seconds="$remaining_seconds"
    sleep "$sleep_seconds"
  done

  "$USER_RUN_AWS_CLI" ssm get-command-invocation \
    --command-id "$command_id" --instance-id "$instance_id" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query StandardOutputContent --output text >"$output_file"
  chmod 0600 "$output_file"
  if [[ -s "$output_file" ]]; then
    sed -n '1,20p' "$output_file"
  fi
  printf '%s\n' 'user-run SSM command: PASS' >&2
)
