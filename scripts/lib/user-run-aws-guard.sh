#!/usr/bin/env bash

require_user_run_aws() {
  local approval_variable="$1"
  local approval_value="${!approval_variable:-0}"
  if [[ "$approval_value" != "1" ]]; then
    printf 'ERROR: set %s=1 for this explicit user-run AWS operation.\n' "$approval_variable" >&2
    return 2
  fi

  local ambient_credential_vars=(
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
  local variable_name
  for variable_name in "${ambient_credential_vars[@]}"; do
    if [[ -n "${!variable_name:-}" ]]; then
      printf 'ERROR: unset ambient AWS or Terraform override variables before this user-run operation.\n' >&2
      return 2
    fi
  done
  while IFS= read -r variable_name; do
    case "$variable_name" in
      AWS_ENDPOINT_URL|AWS_ENDPOINT_URL_*)
        printf '%s\n' 'ERROR: unset every AWS endpoint override before this user-run operation.' >&2
        return 2
        ;;
      TF_WORKSPACE|TF_DATA_DIR|TF_CLI_ARGS|TF_CLI_ARGS_*)
        if [[ -n "${!variable_name:-}" ]]; then
          printf 'ERROR: unset ambient AWS or Terraform override variables before this user-run operation.\n' >&2
          return 2
        fi
        ;;
    esac
  done < <(compgen -e)

  export AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true

  [[ -n "${AWS_PROFILE:-}" ]] || {
    printf '%s\n' 'ERROR: AWS_PROFILE is required.' >&2
    return 2
  }
  [[ "${AWS_REGION:-}" == "us-east-1" ]] || {
    printf '%s\n' 'ERROR: AWS_REGION must be us-east-1.' >&2
    return 2
  }
  if [[ -n "${AWS_DEFAULT_REGION:-}" && "$AWS_DEFAULT_REGION" != "us-east-1" ]]; then
    printf '%s\n' 'ERROR: AWS_DEFAULT_REGION must be unset or us-east-1.' >&2
    return 2
  fi

  USER_RUN_AWS_CLI="${AWS_CLI:-aws}"
  USER_RUN_TERRAFORM="${TERRAFORM:-terraform}"
  command -v "$USER_RUN_AWS_CLI" >/dev/null 2>&1 || [[ -x "$USER_RUN_AWS_CLI" ]] || {
    printf '%s\n' 'ERROR: AWS CLI is required.' >&2
    return 2
  }
  command -v "$USER_RUN_TERRAFORM" >/dev/null 2>&1 || [[ -x "$USER_RUN_TERRAFORM" ]] || {
    printf '%s\n' 'ERROR: Terraform is required.' >&2
    return 2
  }

  USER_RUN_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
  USER_RUN_TF_ROOT="$USER_RUN_REPO_ROOT/infrastructure/terraform"
  [[ "$(basename "$USER_RUN_REPO_ROOT")" == "aws-glue-postgres-mongodb-lab" ]] || {
    printf '%s\n' 'ERROR: unexpected repository root.' >&2
    return 2
  }
  [[ "$(git -C "$USER_RUN_REPO_ROOT" rev-parse --show-toplevel)" == "$USER_RUN_REPO_ROOT" ]] || {
    printf '%s\n' 'ERROR: run from the exact cloned lab repository.' >&2
    return 2
  }
  [[ -z "$(git -C "$USER_RUN_REPO_ROOT" status --short)" ]] || {
    printf '%s\n' 'ERROR: repository must be clean for user-run AWS operations.' >&2
    return 2
  }

  local state_file="$USER_RUN_TF_ROOT/terraform.tfstate"
  [[ -f "$state_file" && ! -L "$state_file" ]] || {
    printf '%s\n' 'ERROR: exact local Terraform state is required.' >&2
    return 2
  }
  local workspace
  workspace="$($USER_RUN_TERRAFORM -chdir="$USER_RUN_TF_ROOT" workspace show)"
  [[ "$workspace" == "default" ]] || {
    printf '%s\n' 'ERROR: Terraform workspace must be default.' >&2
    return 2
  }

  local state_region state_account current_account
  state_region="$($USER_RUN_TERRAFORM -chdir="$USER_RUN_TF_ROOT" output -raw aws_region)"
  state_account="$($USER_RUN_TERRAFORM -chdir="$USER_RUN_TF_ROOT" output -raw aws_account_id)"
  [[ "$state_region" == "us-east-1" && -n "$state_account" ]] || {
    printf '%s\n' 'ERROR: Terraform state identity is incomplete or outside us-east-1.' >&2
    return 2
  }

  export AWS_EC2_METADATA_DISABLED=true
  export AWS_DEFAULT_REGION=us-east-1
  current_account="$($USER_RUN_AWS_CLI --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    sts get-caller-identity --query Account --output text)"
  [[ "$current_account" == "$state_account" ]] || {
    printf '%s\n' 'ERROR: AWS account does not match the exact local Terraform state.' >&2
    return 2
  }
}
