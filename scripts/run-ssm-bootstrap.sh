#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tf_root="$repo_root/infrastructure/terraform"
terraform_bin="${TERRAFORM:-terraform}"
aws_cli="${AWS_CLI:-aws}"

: "${AWS_PROFILE:?Set AWS_PROFILE to a personal lab profile.}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ "$aws_region" != "us-east-1" ]]; then
  printf 'ERROR: set AWS_REGION=us-east-1 for this lab.\n' >&2
  exit 1
fi

instance_id="$($terraform_bin -chdir="$tf_root" output -raw database_instance_id)"
command_id="$($aws_cli --profile "$AWS_PROFILE" --region "$aws_region" ssm send-command \
  --instance-ids "$instance_id" \
  --document-name AWS-RunShellScript \
  --timeout-seconds 900 \
  --comment 'aws-glue-postgres-mongodb-lab database bootstrap' \
  --parameters 'commands=["sudo -u ec2-user env AWS_REGION=us-east-1 /opt/aws-glue-postgres-mongodb-lab/scripts/bootstrap-ec2.sh"]' \
  --query 'Command.CommandId' --output text)"

printf 'Waiting for scoped SSM command %s on %s...\n' "$command_id" "$instance_id"
if ! "$aws_cli" --profile "$AWS_PROFILE" --region "$aws_region" ssm wait command-executed \
  --command-id "$command_id" --instance-id "$instance_id"; then
  status="$($aws_cli --profile "$AWS_PROFILE" --region "$aws_region" ssm get-command-invocation \
    --command-id "$command_id" --instance-id "$instance_id" --query Status --output text)"
  printf 'ERROR: SSM bootstrap did not succeed; status is %s. Inspect invocation %s.\n' \
    "$status" "$command_id" >&2
  exit 1
fi
status="$($aws_cli --profile "$AWS_PROFILE" --region "$aws_region" ssm get-command-invocation \
  --command-id "$command_id" --instance-id "$instance_id" --query Status --output text)"
if [[ "$status" != "Success" ]]; then
  printf 'ERROR: SSM bootstrap status is %s. Inspect invocation output in AWS.\n' "$status" >&2
  exit 1
fi
printf 'aws-glue-postgres-mongodb-lab SSM bootstrap: PASS\n'
