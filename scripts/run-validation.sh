#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/lib/user-run-aws-guard.sh"
source "$script_dir/lib/user-run-ssm.sh"
require_user_run_aws APPROVE_GLUE_VALIDATE

remote_command='sudo -u ec2-user python3 /opt/aws-glue-postgres-mongodb-lab/validation/reconcile.py --output /var/tmp/aws-glue-postgres-mongodb-lab/reconciliation-summary.json'
run_user_ssm_command "$remote_command"
printf '%s\n' 'validate: PASS (redacted summary written mode 0600 on EC2)'
