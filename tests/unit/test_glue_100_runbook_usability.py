from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def section(document: str, start: str, end: str | None = None) -> str:
    body = document.split(start, 1)[1]
    return body if end is None else body.split(end, 1)[0]


def test_roadmap_documents_the_remaining_bounded_plan() -> None:
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()

    assert "| `GLUE-090` | DONE | [#12]" in roadmap
    assert "| `GLUE-100` | DONE | [#13]" in roadmap
    assert "agent/hermes-codex/glue-100-runbook-03-04-usability" in roadmap
    assert "| `GLUE-110` | IN PROGRESS |" in roadmap
    assert "agent/hermes-codex/glue-110-runbook-05-07-usability" in roadmap


def test_glue_configuration_runbook_teaches_and_verifies_each_object() -> None:
    runbook = (ROOT / "docs/runbook/03-CONFIGURE-GLUE.md").read_text()
    identity = section(
        runbook,
        "## Step 1 — Select the personal lab identity",
        "## Step 2 — Deploy the Glue artifacts",
    )
    connections = section(
        runbook,
        "## Step 3 — Inspect both connection definitions safely",
        "## Step 4 — Run the unscheduled crawler and assert the catalog",
    )
    crawler = section(runbook, "## Step 4 — Run the unscheduled crawler and assert the catalog")

    for term in ("connection", "crawler", "Data Catalog", "job"):
        assert term in runbook
    assert "make doctor" in identity
    assert "aws sts get-caller-identity" in identity
    assert "connection definitions: PASS" in connections
    assert '"SECRET_ID"' in connections
    assert '"USERNAME"' in connections and '"PASSWORD"' in connections
    assert (
        crawler.count(
            'CRAWLER="$(terraform -chdir=infrastructure/terraform output -raw glue_crawler_name)"'
        )
        >= 2
    )
    assert "LastError:LastCrawl.ErrorMessage" in crawler


def test_migration_runbook_uses_exact_local_and_ssm_verification() -> None:
    runbook = (ROOT / "docs/runbook/04-RUN-MIGRATION.md").read_text()
    prerequisites = section(
        runbook,
        "## Step 1 — Confirm migration prerequisites",
        "## Step 2 — Run and wait for the snapshot job",
    )
    job = section(
        runbook,
        "## Step 2 — Run and wait for the snapshot job",
        "## Step 3 — Open the database-host session",
    )
    session = section(
        runbook,
        "## Step 3 — Open the database-host session",
        "## Step 4 — Inspect a redacted MongoDB summary",
    )

    assert "PYTEST=.venv/bin/pytest" in prerequisites
    assert "RUFF=.venv/bin/ruff" in prerequisites
    assert "aws logs tail /aws-glue/jobs/error" in job
    assert '--profile "$AWS_PROFILE" --region "$AWS_REGION"' in job
    assert "database-host session: PASS" in session
    assert "unset INSTANCE_ID" in session


def test_mongodb_inspection_proves_cleanup_inside_the_secret_scope() -> None:
    runbook = (ROOT / "docs/runbook/04-RUN-MIGRATION.md").read_text()
    inspection = section(runbook, "## Step 4 — Inspect a redacted MongoDB summary")

    assert "jq -er" in inspection
    assert "cleanup_mongo_secret_vars" in inspection
    assert "temporary secret variables removed: PASS" in inspection
    assert inspection.index("cleanup_mongo_secret_vars") < inspection.index(
        "temporary secret variables removed: PASS"
    )
    assert "That roadmap task remains not started" not in inspection
