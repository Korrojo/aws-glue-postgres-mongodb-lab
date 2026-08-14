from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "docker" / "compose.yaml"

POSTGRES_IMAGE = (
    "postgres:16.15-bookworm@"
    "sha256:60f4761b9035e0b8d5218f701a8c3382f641bf12b1604822574cf5be3baeb537"
)
MONGODB_IMAGE = (
    "mongo:8.0.29-noble@sha256:43f6e6733f0f0647bcc896cd7b4ee6e0e4872e65a1e6de27ea935efd43120a70"
)


def load_compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE_PATH.read_text())


def test_compose_uses_only_the_two_pinned_multiarch_database_images() -> None:
    compose = load_compose()
    services = compose["services"]

    assert compose["name"] == "aws-glue-postgres-mongodb-lab"
    assert set(services) == {"postgres", "mongodb"}
    assert services["postgres"]["image"] == POSTGRES_IMAGE
    assert services["mongodb"]["image"] == MONGODB_IMAGE
    assert "platform" not in services["postgres"]
    assert "platform" not in services["mongodb"]


def test_compose_requires_runtime_credentials_and_defaults_to_loopback() -> None:
    compose = load_compose()
    services = compose["services"]

    assert services["postgres"]["ports"] == ["${DATABASE_BIND_ADDRESS:-127.0.0.1}:5432:5432"]
    assert services["mongodb"]["ports"] == ["${DATABASE_BIND_ADDRESS:-127.0.0.1}:27017:27017"]

    postgres_environment = services["postgres"]["environment"]
    mongodb_environment = services["mongodb"]["environment"]
    for variable in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        assert postgres_environment[variable] == f"${{{variable}:?set {variable} in .env}}"
    for variable in (
        "MONGO_INITDB_ROOT_USERNAME",
        "MONGO_INITDB_ROOT_PASSWORD",
        "MONGO_DATABASE",
        "MONGO_GLUE_USERNAME",
        "MONGO_GLUE_PASSWORD",
    ):
        assert mongodb_environment[variable] == f"${{{variable}:?set {variable} in .env}}"


def test_compose_has_health_checks_named_volumes_and_read_only_initializers() -> None:
    compose = load_compose()
    services = compose["services"]

    assert set(compose["volumes"]) == {"postgres_data", "mongodb_data"}
    assert services["postgres"]["volumes"] == [
        "postgres_data:/var/lib/postgresql/data",
        "./postgres/init:/docker-entrypoint-initdb.d:ro",
        "./postgres/invalid:/lab-invalid-fixtures:ro",
    ]
    assert services["mongodb"]["volumes"] == [
        "mongodb_data:/data/db",
        "./mongodb/init:/docker-entrypoint-initdb.d:ro",
    ]
    for service in services.values():
        healthcheck = service["healthcheck"]
        assert healthcheck["interval"] == "5s"
        assert healthcheck["timeout"] == "5s"
        assert healthcheck["retries"] == 20
        assert healthcheck["start_period"] == "10s"


def test_source_schema_and_fixtures_cover_the_design_contract() -> None:
    schema = (ROOT / "docker/postgres/init/01-schema.sql").read_text()
    seed = (ROOT / "docker/postgres/init/02-seed.sql").read_text()
    assertions = (ROOT / "docker/postgres/init/03-assert-valid.sql").read_text()

    for required in (
        "CREATE SCHEMA sales",
        "CREATE TABLE sales.orders",
        "CREATE TABLE sales.order_items",
        "PRIMARY KEY",
        "FOREIGN KEY",
        "UNIQUE (order_id, line_number)",
        "CHECK (quantity > 0)",
        "CHECK (unit_price >= 0)",
        "NUMERIC(12,2)",
        "TIMESTAMPTZ",
        "is_deleted",
    ):
        assert required in schema

    assert seed.count("INSERT INTO sales.orders") == 1
    assert seed.count("INSERT INTO sales.order_items") == 1
    for fixture_marker in (
        "mixed-case-email",
        "multiple-items",
        "single-item",
        "offset-timestamp",
        "soft-deleted-order",
        "soft-deleted-item",
        "decimal-total",
    ):
        assert fixture_marker in seed

    for invariant in (
        "orders_total=5",
        "active_orders=4",
        "items_total=9",
        "active_items_for_active_orders=7",
        "orphan_items=0",
        "duplicate_line_numbers=0",
        "invalid_quantities=0",
        "invalid_prices=0",
        "source assertions: PASS",
    ):
        assert invariant in assertions


def test_invalid_fixtures_are_isolated_and_expected_to_fail() -> None:
    invalid_dir = ROOT / "docker/postgres/invalid"
    fixtures = sorted(path.name for path in invalid_dir.glob("*.sql"))

    assert fixtures == [
        "duplicate-line-number.sql",
        "invalid-price.sql",
        "invalid-quantity.sql",
        "orphan-item.sql",
    ]
    for fixture in fixtures:
        content = (invalid_dir / fixture).read_text()
        assert "BEGIN;" in content
        assert "ROLLBACK;" in content
        assert "INSERT INTO sales.order_items" in content


def test_mongodb_initializer_creates_only_the_lab_writer() -> None:
    initializer = (ROOT / "docker/mongodb/init/01-create-glue-user.sh").read_text()

    assert "set -euo pipefail" in initializer
    assert "db.getSiblingDB(process.env.MONGO_DATABASE)" in initializer
    assert "readWrite" in initializer
    assert "process.env.MONGO_GLUE_PASSWORD" in initializer
    assert "migration_lab" not in initializer
    assert "printenv" not in initializer


def test_make_and_ci_own_the_complete_local_lifecycle() -> None:
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    for target in ("local-up", "local-status", "local-test", "local-down"):
        assert f"{target}:" in makefile
    assert "local-up local-status local-test local-down:" not in makefile
    assert "docker compose" in makefile
    assert "Data-layer container smoke test" in workflow
    for command in (
        "make compose-check",
        "make local-up",
        "make local-test",
        "make local-down RESET_VOLUMES=1",
    ):
        assert command in workflow


def test_database_runbook_replaces_the_template_with_executable_sections() -> None:
    runbook = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()

    assert "Status: implemented by `GLUE-010` and `GLUE-020`" in runbook
    assert "## Required completed sections" not in runbook
    assert "## Optional — Run the data layer on the Mac" in runbook
    assert "glue_username" not in runbook
    assert "glue_password" not in runbook
    assert 'mongodb["username"]' in runbook
    assert 'mongodb["password"]' in runbook
    assert "rm -f .env" in runbook
    for field in (
        "**Purpose**",
        "**Run from**",
        "**Prerequisites**",
        "**Inputs**",
        "**Command**",
        "**Expected result**",
        "**Verify**",
        "**Repeat, reset, or rollback**",
        "**If it fails**",
        "**Next**",
    ):
        assert field in runbook
