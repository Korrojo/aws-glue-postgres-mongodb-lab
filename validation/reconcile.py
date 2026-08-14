#!/usr/bin/env python3
"""USER-RUN ONLY EC2 reconciliation entrypoint.

The program retrieves the two connector secrets into process memory, queries the exact
Compose containers through stdin-only authentication, and gives bounded projections to
the pure reconciliation core.  It never prints credentials, endpoints, identifiers, or
full records.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

PROJECT = "aws-glue-postgres-mongodb-lab"
REGION = "us-east-1"
REPO_ROOT = Path(f"/opt/{PROJECT}")
COMPOSE_FILE = REPO_ROOT / "docker/compose.yaml"
POSTGRES_SECRET = f"/{PROJECT}/postgres"
MONGODB_SECRET = f"/{PROJECT}/mongodb-glue"
DEFAULT_OUTPUT = Path(f"/var/tmp/{PROJECT}/reconciliation-summary.json")
MAX_ORDERS = 100
MAX_ITEMS = 1000
Run = Callable[..., subprocess.CompletedProcess[str]]

if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
try:
    from glue_lab.validation import reconcile_summaries, write_redacted_result
except ModuleNotFoundError:  # Supports credential-free execution from a development checkout.
    local_src = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(local_src))
    from glue_lab.validation import reconcile_summaries, write_redacted_result


class BoundaryError(RuntimeError):
    """A redacted service-boundary contract failure."""


SOURCE_SQL = r"""
WITH active_orders AS (
    SELECT * FROM sales.orders WHERE is_deleted = FALSE
), active_items AS (
    SELECT i.*
    FROM sales.order_items AS i
    JOIN active_orders AS o USING (order_id)
    WHERE i.is_deleted = FALSE
), bounded_items AS (
    SELECT * FROM active_items ORDER BY order_id, line_number LIMIT 1001
), bounded_orders AS (
    SELECT * FROM active_orders ORDER BY order_id LIMIT 101
), order_projection AS (
    SELECT
        o.order_id,
        json_build_object(
            'order_id', o.order_id,
            'customer', json_build_object(
                'id', o.customer_id,
                'name', concat_ws(' ', btrim(o.customer_first_name), btrim(o.customer_last_name)),
                'email', lower(btrim(o.customer_email))
            ),
            'ordered_at', to_char(o.ordered_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            'updated_at', to_char(o.updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            'status', upper(btrim(o.order_status)),
            'items', COALESCE((
                SELECT json_agg(json_build_object(
                    'id', i.order_item_id,
                    'line_number', i.line_number,
                    'sku', btrim(i.sku),
                    'quantity', i.quantity,
                    'unit_price', i.unit_price::text,
                    'line_total', (i.quantity * i.unit_price)::text
                ) ORDER BY i.line_number)
                FROM bounded_items AS i WHERE i.order_id = o.order_id
            ), '[]'::json),
            'order_total', COALESCE((
                SELECT sum(i.quantity * i.unit_price)::text
                FROM active_items AS i WHERE i.order_id = o.order_id
            ), '0')
        ) AS document
    FROM bounded_orders AS o
)
SELECT json_build_object(
    'active_order_count', (SELECT count(*) FROM active_orders),
    'active_item_count', (SELECT count(*) FROM active_items),
    'deleted_order_count', (SELECT count(*) FROM sales.orders WHERE is_deleted = TRUE),
    'deleted_item_count', (SELECT count(*) FROM sales.order_items WHERE is_deleted = TRUE),
    'orders', COALESCE((
        SELECT json_agg(document ORDER BY order_id) FROM order_projection
    ), '[]'::json),
    'deleted_order_ids', COALESCE((
        SELECT json_agg(order_id ORDER BY order_id)
        FROM (
            SELECT order_id FROM sales.orders
            WHERE is_deleted = TRUE ORDER BY order_id LIMIT 101
        ) AS d
    ), '[]'::json),
    'deleted_item_ids', COALESCE((
        SELECT json_agg(order_item_id ORDER BY order_item_id)
        FROM (SELECT order_item_id FROM sales.order_items WHERE is_deleted = TRUE
              ORDER BY order_item_id LIMIT 1001) AS d
    ), '[]'::json)
);
"""


def _completed(
    arguments: list[str],
    *,
    input_text: str | None,
    run: Run,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = run(
            arguments,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
    except OSError as error:
        raise BoundaryError("required local command is unavailable") from error
    if result.returncode != 0:
        raise BoundaryError("service boundary command failed")
    return result


def validate_secret(payload: object, kind: str) -> dict[str, Any]:
    expected = {"host", "port", "database", "username", "password"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise BoundaryError(f"{kind} secret schema is invalid")
    if any(value in (None, "") for value in payload.values()):
        raise BoundaryError(f"{kind} secret schema is invalid")
    expected_port = 5432 if kind == "postgres" else 27017
    if payload["port"] not in (expected_port, str(expected_port)):
        raise BoundaryError(f"{kind} secret schema is invalid")
    return payload


def load_secret(
    secret_name: str, kind: str, *, aws_cli: str = "aws", run: Run = subprocess.run
) -> dict[str, Any]:
    ambient_credentials = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    }
    if any(name in os.environ for name in ambient_credentials) or any(
        name == "AWS_ENDPOINT_URL" or name.startswith("AWS_ENDPOINT_URL_") for name in os.environ
    ):
        raise BoundaryError("ambient AWS credential or endpoint override is not allowed")
    environment = os.environ.copy()
    environment["AWS_IGNORE_CONFIGURED_ENDPOINT_URLS"] = "true"
    result = _completed(
        [
            aws_cli,
            "--region",
            REGION,
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_name,
            "--query",
            "SecretString",
            "--output",
            "text",
        ],
        input_text=None,
        run=run,
        environment=environment,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise BoundaryError(f"{kind} secret schema is invalid") from error
    return validate_secret(payload, kind)


def resolve_container(service: str, *, run: Run = subprocess.run) -> str:
    if service not in {"postgres", "mongodb"}:
        raise BoundaryError("unexpected Compose service")
    result = _completed(
        [
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "-f",
            str(COMPOSE_FILE),
            "ps",
            "-q",
            service,
        ],
        input_text=None,
        run=run,
    )
    container_id = result.stdout.strip()
    if not container_id or "\n" in container_id:
        raise BoundaryError("exact Compose container is not running")
    inspected = _completed(
        ["docker", "inspect", "--format", "{{.Name}}", container_id],
        input_text=None,
        run=run,
    ).stdout.strip()
    if inspected != f"/{PROJECT}-{service}-1":
        raise BoundaryError("Compose container identity does not match the fixed project")
    return container_id


def _parse_single_json(output: str, label: str) -> dict[str, Any]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise BoundaryError(f"{label} returned an invalid bounded summary")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise BoundaryError(f"{label} returned an invalid bounded summary") from error
    if not isinstance(payload, dict):
        raise BoundaryError(f"{label} returned an invalid bounded summary")
    return payload


def validate_source_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "active_order_count",
        "active_item_count",
        "deleted_order_count",
        "deleted_item_count",
        "orders",
        "deleted_order_ids",
        "deleted_item_ids",
    }
    if set(payload) != required:
        raise BoundaryError("source returned an invalid bounded summary")
    counts = [
        payload["active_order_count"],
        payload["active_item_count"],
        payload["deleted_order_count"],
        payload["deleted_item_count"],
    ]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
        raise BoundaryError("source returned an invalid bounded summary")
    if payload["active_order_count"] > MAX_ORDERS or payload["deleted_order_count"] > MAX_ORDERS:
        raise BoundaryError("source exceeds the bounded order summary limit")
    if payload["active_item_count"] > MAX_ITEMS or payload["deleted_item_count"] > MAX_ITEMS:
        raise BoundaryError("source exceeds the bounded item summary limit")
    for name in ("orders", "deleted_order_ids", "deleted_item_ids"):
        if not isinstance(payload[name], list):
            raise BoundaryError("source returned an invalid bounded summary")
    if len(payload["orders"]) != payload["active_order_count"]:
        raise BoundaryError("source returned an invalid bounded summary")
    if len(payload["deleted_order_ids"]) != payload["deleted_order_count"]:
        raise BoundaryError("source returned an invalid bounded summary")
    if len(payload["deleted_item_ids"]) != payload["deleted_item_count"]:
        raise BoundaryError("source returned an invalid bounded summary")
    projected_items = sum(
        len(order.get("items", [])) if isinstance(order, dict) else 0 for order in payload["orders"]
    )
    if projected_items != payload["active_item_count"]:
        raise BoundaryError("source returned an invalid bounded summary")
    return {
        "orders": payload["orders"],
        "deleted_order_ids": payload["deleted_order_ids"],
        "deleted_item_ids": payload["deleted_item_ids"],
    }


def read_source(
    secret: dict[str, Any], container_id: str, *, run: Run = subprocess.run
) -> dict[str, Any]:
    shell = (
        "IFS= read -r PGUSER; IFS= read -r PGPASSWORD; IFS= read -r PGDATABASE; "
        "export PGUSER PGPASSWORD PGDATABASE; "
        "exec psql --host 127.0.0.1 --port 5432 --no-password --tuples-only --no-align --quiet"
    )
    stdin = (
        f"{secret['username']}\n{secret['password']}\n{secret['database']}\n{SOURCE_SQL.strip()}\n"
    )
    result = _completed(
        ["docker", "exec", "-i", container_id, "sh", "-eu", "-c", shell],
        input_text=stdin,
        run=run,
    )
    return validate_source_payload(_parse_single_json(result.stdout, "PostgreSQL"))


def _mongo_program(secret: dict[str, Any]) -> str:
    auth = json.dumps(
        {
            "database": secret["database"],
            "username": secret["username"],
            "password": secret["password"],
        },
        separators=(",", ":"),
    )
    return f"""
const auth = {auth};
const target = db.getSiblingDB(auth.database);
if (!target.auth(auth.username, auth.password)) {{ quit(2); }}
const targetDocumentCount = target.orders.countDocuments({{}});
const itemCountRows = target.orders.aggregate([
  {{$project: {{count: {{$size: {{$ifNull: ["$items", []]}}}}}}}},
  {{$group: {{_id: null, count: {{$sum: "$count"}}}}}}
]).toArray();
const targetItemCount = itemCountRows.length === 0 ? 0 : itemCountRows[0].count;
if (targetDocumentCount > 100 || targetItemCount > 1000) {{ quit(4); }}
const documents = target.orders.find({{}}, {{
  _id: 1, customer: 1, orderedAt: 1, updatedAt: 1, status: 1,
  items: 1, orderTotal: 1, migration: 1
}}).sort({{_id: 1}}).limit(101).toArray().map((document) => ({{
  _id: Number(document._id),
  customer: {{
    id: Number(document.customer.id),
    name: document.customer.name,
    email: document.customer.email
  }},
  orderedAt: document.orderedAt,
  updatedAt: document.updatedAt,
  status: document.status,
  items: (document.items || []).slice(0, 1001).map((item) => ({{
    id: Number(item.id), lineNumber: Number(item.lineNumber), sku: item.sku,
    quantity: Number(item.quantity), unitPrice: String(item.unitPrice),
    lineTotal: String(item.lineTotal)
  }})),
  orderTotal: String(document.orderTotal),
  migration: document.migration
}}));
print(JSON.stringify({{
  target_document_count: Number(targetDocumentCount),
  target_item_count: Number(targetItemCount),
  documents: documents
}}));
""".strip()


def validate_target_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"target_document_count", "target_item_count", "documents"}:
        raise BoundaryError("target returned an invalid bounded summary")
    document_count = payload["target_document_count"]
    item_count = payload["target_item_count"]
    if (
        isinstance(document_count, bool)
        or not isinstance(document_count, int)
        or isinstance(item_count, bool)
        or not isinstance(item_count, int)
        or document_count < 0
        or item_count < 0
    ):
        raise BoundaryError("target returned an invalid bounded summary")
    if document_count > MAX_ORDERS or item_count > MAX_ITEMS:
        raise BoundaryError("target exceeds the bounded summary limit")
    documents = payload["documents"]
    if not isinstance(documents, list) or len(documents) != document_count:
        raise BoundaryError("target returned an invalid bounded summary")
    projected_items = sum(
        len(document.get("items", [])) if isinstance(document, dict) else 0
        for document in documents
    )
    if projected_items != item_count:
        raise BoundaryError("target returned an invalid bounded summary")
    return {"documents": documents}


def read_target(
    secret: dict[str, Any], container_id: str, *, run: Run = subprocess.run
) -> dict[str, Any]:
    result = _completed(
        ["docker", "exec", "-i", container_id, "mongosh", "--quiet", "--norc"],
        input_text=_mongo_program(secret) + "\n",
        run=run,
    )
    return validate_target_payload(_parse_single_json(result.stdout, "MongoDB"))


def _boundary_failure() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "passed": False,
        "counts": {
            "active_source_orders": 0,
            "active_source_items": 0,
            "target_documents": 0,
            "target_embedded_items": 0,
        },
        "mismatch_categories": {"boundary_error": 1},
        "mismatch_count": 1,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile bounded synthetic lab summaries.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    try:
        postgres_secret = load_secret(POSTGRES_SECRET, "postgres")
        mongodb_secret = load_secret(MONGODB_SECRET, "mongodb")
        postgres_container = resolve_container("postgres")
        mongodb_container = resolve_container("mongodb")
        source = read_source(postgres_secret, postgres_container)
        target = read_target(mongodb_secret, mongodb_container)
        result = reconcile_summaries(source, target)
    except BoundaryError:
        result = _boundary_failure()
        write_redacted_result(arguments.output, result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        print(
            "ERROR: reconciliation service boundary failed; identifiers redacted.",
            file=sys.stderr,
        )
        return 2
    finally:
        for name in ("postgres_secret", "mongodb_secret"):
            if name in locals():
                locals()[name].clear()

    write_redacted_result(arguments.output, result)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
