#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/lib/user-run-aws-guard.sh"
require_user_run_aws APPROVE_LAB_COST_CHECK

aws_cli="$USER_RUN_AWS_CLI"
tf="$USER_RUN_TERRAFORM"
project='aws-glue-postgres-mongodb-lab'
common=(--profile "$AWS_PROFILE" --region "$AWS_REGION" --output text)

bucket="$($tf -chdir="$USER_RUN_TF_ROOT" output -raw artifact_bucket_name)"
state_resource_count="$($tf -chdir="$USER_RUN_TF_ROOT" state list | python3 -c 'import sys; print(sum(bool(line.strip()) for line in sys.stdin))')"
tagged_count="$($aws_cli resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=$project" 'Key=Environment,Values=lab' 'Key=ManagedBy,Values=terraform' \
  "${common[@]}" --query 'length(ResourceTagMappingList)')"
instance_count="$($aws_cli ec2 describe-instances \
  --filters "Name=tag:Project,Values=$project" 'Name=tag:Environment,Values=lab' \
  'Name=instance-state-name,Values=pending,running,stopping,stopped' \
  "${common[@]}" --query 'length(Reservations[].Instances[])')"
endpoint_count="$($aws_cli ec2 describe-vpc-endpoints \
  --filters "Name=tag:Project,Values=$project" 'Name=tag:Environment,Values=lab' \
  "${common[@]}" --query 'length(VpcEndpoints)')"
job_count="$($aws_cli glue get-jobs "${common[@]}" \
  --query "length(Jobs[?Name=='$project-orders-to-mongodb'])")"
crawler_count="$($aws_cli glue get-crawlers "${common[@]}" \
  --query "length(Crawlers[?Name=='$project-orders'])")"
connection_count="$($aws_cli glue get-connections "${common[@]}" \
  --query "length(ConnectionList[?Name=='$project-postgres' || Name=='$project-mongodb'])")"
database_count="$($aws_cli glue get-databases "${common[@]}" \
  --query "length(DatabaseList[?Name=='aws_glue_postgres_mongodb_lab'])")"
secret_count="$($aws_cli secretsmanager list-secrets "${common[@]}" \
  --query "length(SecretList[?Name=='/$project/postgres' || Name=='/$project/mongodb' || Name=='/$project/mongodb-glue'])")"
role_count="$($aws_cli iam list-roles "${common[@]}" \
  --query "length(Roles[?RoleName=='$project-ec2' || RoleName=='$project-glue'])")"
bucket_count="$($aws_cli s3api list-buckets "${common[@]}" \
  --query "length(Buckets[?Name=='$bucket'])")"

python3 - "$state_resource_count" "$tagged_count" "$instance_count" "$endpoint_count" \
  "$job_count" "$crawler_count" "$connection_count" "$database_count" "$secret_count" \
  "$role_count" "$bucket_count" <<'PY'
import json
import sys
names = (
    "terraform_state_addresses", "project_tagged_resources", "ec2_instances",
    "vpc_endpoints", "glue_jobs", "glue_crawlers", "glue_connections",
    "glue_databases", "secrets", "iam_roles", "artifact_buckets",
)
try:
    inventory = dict(zip(names, map(int, sys.argv[1:]), strict=True))
except (TypeError, ValueError):
    raise SystemExit("ERROR: cost inventory returned a nonnumeric result.")
expected = {
    "ec2_instances": 1,
    "vpc_endpoints": 2,
    "glue_jobs": 1,
    "glue_crawlers": 1,
    "glue_connections": 2,
    "glue_databases": 1,
    "secrets": 3,
    "iam_roles": 2,
    "artifact_buckets": 1,
}
if any(inventory[name] != value for name, value in expected.items()):
    raise SystemExit("ERROR: expected-resource inventory is incomplete; identifiers redacted.")
if inventory["terraform_state_addresses"] < 1 or inventory["project_tagged_resources"] < 1:
    raise SystemExit("ERROR: project inventory is unexpectedly empty.")
print(json.dumps({"schema_version": 1, "passed": True, "counts": inventory}, sort_keys=True, separators=(",", ":")))
PY
printf '%s\n' 'cost-check: PASS (expected project inventory only; no Cost Explorer query)'
