#!/usr/bin/env python3
"""USER-RUN ONLY fixed-fixture controls for the bounded rerun proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from reconcile import (
    MONGODB_SECRET,
    POSTGRES_SECRET,
    BoundaryError,
    load_secret,
    read_target,
    resolve_container,
)

PROJECT = "aws-glue-postgres-mongodb-lab"
DEFAULT_FINGERPRINT = Path(f"/var/tmp/{PROJECT}/rerun-fingerprint.json")
DEFAULT_RECONCILIATION = Path(f"/var/tmp/{PROJECT}/reconciliation-summary.json")

SQL_ACTIONS = {
    "apply-update": """
BEGIN;
UPDATE sales.orders
SET order_status = ' rerun-replaced ', updated_at = '2026-08-01 12:10:00-04'
WHERE order_id = 1001 AND is_deleted = FALSE;
UPDATE sales.order_items
SET quantity = 2, updated_at = '2026-08-01 12:05:00-04'
WHERE order_item_id = 5002 AND order_id = 1001 AND is_deleted = FALSE;
DO $$ BEGIN
  IF (SELECT count(*) FROM sales.orders
      WHERE order_id = 1001 AND order_status = ' rerun-replaced ') <> 1
     OR (SELECT count(*) FROM sales.order_items
         WHERE order_item_id = 5002 AND quantity = 2) <> 1 THEN
    RAISE EXCEPTION 'controlled fixture update failed';
  END IF;
END $$;
COMMIT;
""",
    "reset-update": """
BEGIN;
UPDATE sales.orders
SET order_status = ' shipped ', updated_at = '2026-08-01 11:10:00-04'
WHERE order_id = 1001;
UPDATE sales.order_items
SET quantity = 1, updated_at = '2026-08-01 11:05:00-04'
WHERE order_item_id = 5002 AND order_id = 1001;
COMMIT;
""",
    "soft-delete": """
BEGIN;
UPDATE sales.orders
SET is_deleted = TRUE, updated_at = '2026-08-03 10:05:00+09'
WHERE order_id = 1003 AND is_deleted = FALSE;
DO $$ BEGIN
  IF (SELECT count(*) FROM sales.orders WHERE order_id = 1003 AND is_deleted = TRUE) <> 1 THEN
    RAISE EXCEPTION 'controlled soft delete failed';
  END IF;
END $$;
COMMIT;
""",
    "restore-source": """
BEGIN;
UPDATE sales.orders
SET is_deleted = FALSE, updated_at = '2026-08-03 09:05:00+09'
WHERE order_id = 1003;
COMMIT;
""",
}


def _run_postgres(action: str) -> None:
    secret = load_secret(POSTGRES_SECRET, "postgres")
    try:
        container = resolve_container("postgres")
        shell = (
            "IFS= read -r PGUSER; IFS= read -r PGPASSWORD; IFS= read -r PGDATABASE; "
            "export PGUSER PGPASSWORD PGDATABASE; "
            "exec psql --host 127.0.0.1 --port 5432 --no-password --quiet "
            "--set ON_ERROR_STOP=1 >/dev/null"
        )
        stdin = (
            f"{secret['username']}\n{secret['password']}\n{secret['database']}\n"
            f"{SQL_ACTIONS[action].strip()}\n"
        )
        result = subprocess.run(
            ["docker", "exec", "-i", container, "sh", "-eu", "-c", shell],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise BoundaryError("fixed PostgreSQL fixture operation failed")
    finally:
        secret.clear()


def _delete_stale_target() -> None:
    secret = load_secret(MONGODB_SECRET, "mongodb")
    try:
        container = resolve_container("mongodb")
        auth = json.dumps(
            {
                "database": secret["database"],
                "username": secret["username"],
                "password": secret["password"],
            },
            separators=(",", ":"),
        )
        program = f"""
const auth = {auth};
const target = db.getSiblingDB(auth.database);
if (!target.auth(auth.username, auth.password)) {{ quit(2); }}
const result = target.orders.deleteOne({{_id: 1003}});
if (result.deletedCount !== 1) {{ quit(3); }}
""".strip()
        result = subprocess.run(
            ["docker", "exec", "-i", container, "mongosh", "--quiet", "--norc"],
            input=program + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise BoundaryError("targeted stale-target resolution failed")
    finally:
        secret.clear()


def _write_private(path: Path, payload: dict[str, Any]) -> None:
    from glue_lab.validation import write_redacted_result

    write_redacted_result(path, payload)


def _fingerprint(path: Path) -> dict[str, Any]:
    secret = load_secret(MONGODB_SECRET, "mongodb")
    try:
        target = read_target(secret, resolve_container("mongodb"))
    finally:
        secret.clear()
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":")).encode()
    item_count = sum(len(document["items"]) for document in target["documents"])
    payload = {
        "schema_version": 1,
        "document_count": len(target["documents"]),
        "embedded_item_count": item_count,
        "business_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    _write_private(path, payload)
    return payload


def _assert_stale(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise BoundaryError("redacted reconciliation result is unavailable") from error
    categories = result.get("mismatch_categories", {})
    if result.get("passed") is not False or not all(
        categories.get(name, 0) >= 1 for name in ("stale_target", "deleted_order_present")
    ):
        raise BoundaryError("expected stale-target mismatch was not detected")
    return {"schema_version": 1, "phase": "stale_target_detection", "passed": True}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one fixed rerun-proof fixture operation.")
    parser.add_argument(
        "action",
        choices=[*SQL_ACTIONS, "delete-stale-target", "fingerprint", "assert-stale"],
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_FINGERPRINT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_RECONCILIATION)
    arguments = parser.parse_args(argv)
    try:
        if arguments.action in SQL_ACTIONS:
            _run_postgres(arguments.action)
            result = {"schema_version": 1, "phase": arguments.action, "passed": True}
        elif arguments.action == "delete-stale-target":
            _delete_stale_target()
            result = {
                "schema_version": 1,
                "phase": "targeted_stale_resolution",
                "passed": True,
            }
        elif arguments.action == "fingerprint":
            result = _fingerprint(arguments.output)
        else:
            result = _assert_stale(arguments.summary)
    except BoundaryError:
        print("ERROR: fixed rerun operation failed; identifiers redacted.", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
