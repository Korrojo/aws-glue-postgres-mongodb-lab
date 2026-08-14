#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/user-run-aws-guard.sh"
require_user_run_aws APPROVE_GLUE_CRAWL
aws_cli="$USER_RUN_AWS_CLI"
terraform_bin="$USER_RUN_TERRAFORM"
timeout_seconds="${CRAWLER_TIMEOUT_SECONDS:-600}"
poll_seconds="${CRAWLER_POLL_SECONDS:-10}"

[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || {
  printf '%s\n' 'ERROR: CRAWLER_TIMEOUT_SECONDS must be a positive integer.' >&2
  exit 2
}
((timeout_seconds <= 1200)) || {
  printf '%s\n' 'ERROR: CRAWLER_TIMEOUT_SECONDS maximum is 1200.' >&2
  exit 2
}
[[ "$poll_seconds" =~ ^[1-9][0-9]*$ ]] || {
  printf '%s\n' 'ERROR: CRAWLER_POLL_SECONDS must be a positive integer.' >&2
  exit 2
}
((poll_seconds <= 60)) || {
  printf '%s\n' 'ERROR: CRAWLER_POLL_SECONDS maximum is 60.' >&2
  exit 2
}

tf_root="$USER_RUN_TF_ROOT"
crawler_name="$($terraform_bin -chdir="$tf_root" output -raw glue_crawler_name)"
database_name="$($terraform_bin -chdir="$tf_root" output -raw glue_catalog_database_name)"
previous_start_time="$($aws_cli glue get-crawler --name "$crawler_name" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'Crawler.LastCrawl.StartTime' --output text)"

if ! "$aws_cli" glue start-crawler --name "$crawler_name" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" >/dev/null 2>&1; then
  printf '%s\n' 'ERROR: crawler could not be started; no existing run will be adopted.' >&2
  exit 1
fi

is_newer_start_time() {
  python3 - "$previous_start_time" "$1" <<'PY'
from datetime import datetime
import sys


def parse(value: str):
    if value in {"", "None", "null"}:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

previous = parse(sys.argv[1])
current = parse(sys.argv[2])
raise SystemExit(0 if current is not None and (previous is None or current > previous) else 1)
PY
}

deadline_epoch=$(($(date +%s) + timeout_seconds))
while :; do
  state="$($aws_cli glue get-crawler --name "$crawler_name" --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" --query 'Crawler.State' --output text)"
  last_start_time="$($aws_cli glue get-crawler --name "$crawler_name" --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" --query 'Crawler.LastCrawl.StartTime' --output text)"
  if [[ "$state" == "READY" ]] && is_newer_start_time "$last_start_time"; then
    last_status="$($aws_cli glue get-crawler --name "$crawler_name" --profile "$AWS_PROFILE" \
      --region "$AWS_REGION" --query 'Crawler.LastCrawl.Status' --output text)"
    [[ "$last_status" == "SUCCEEDED" ]] || {
      printf '%s\n' 'ERROR: the newly started crawler run did not succeed; inspect Glue crawler logs.' >&2
      exit 1
    }
    break
  fi
  now_epoch="$(date +%s)"
  remaining_seconds=$((deadline_epoch - now_epoch))
  ((remaining_seconds > 0)) || {
    printf '%s\n' "ERROR: crawler did not produce a newer crawl result within ${timeout_seconds}s." >&2
    exit 1
  }
  sleep_seconds="$poll_seconds"
  ((sleep_seconds <= remaining_seconds)) || sleep_seconds="$remaining_seconds"
  sleep "$sleep_seconds"
done

tables_json="$(mktemp)"
trap 'rm -f "$tables_json"' EXIT
"$aws_cli" glue get-tables --database-name "$database_name" --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" --output json >"$tables_json"
python3 - "$tables_json" <<'PY'
import json
import sys

expected_schemas = {
    "orders": [
        ("order_id", "bigint"),
        ("customer_id", "bigint"),
        ("customer_first_name", "string"),
        ("customer_last_name", "string"),
        ("customer_email", "string"),
        ("order_status", "string"),
        ("ordered_at", "timestamp"),
        ("updated_at", "timestamp"),
        ("is_deleted", "boolean"),
    ],
    "order_items": [
        ("order_item_id", "bigint"),
        ("order_id", "bigint"),
        ("line_number", "int"),
        ("sku", "string"),
        ("quantity", "int"),
        ("unit_price", "decimal(12,2)"),
        ("updated_at", "timestamp"),
        ("is_deleted", "boolean"),
    ],
}
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
tables = {table["Name"]: table for table in payload.get("TableList", [])}
if set(tables) != set(expected_schemas):
    raise SystemExit("ERROR: expected catalog tables and schemas were not found")
for name, expected in expected_schemas.items():
    actual = [
        (column.get("Name"), column.get("Type"))
        for column in tables[name]["StorageDescriptor"]["Columns"]
    ]
    if actual != expected:
        raise SystemExit(f"ERROR: expected catalog tables and schemas; mismatch for {name}")
PY

printf '%s\n' 'crawl: PASS (exact tables, columns, and types verified; output redacted)'
