from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK_ROOT = ROOT / "docs/runbook"


def section(document: str, start: str, end: str | None = None) -> str:
    body = document.split(start, 1)[1]
    return body if end is None else body.split(end, 1)[0]


def test_roadmap_and_readme_track_the_final_documentation_task() -> None:
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()
    readme = (ROOT / "README.md").read_text()

    assert "| `GLUE-100` | DONE | [#13]" in roadmap
    assert "| `GLUE-110` | PR OPEN | [#14]" in roadmap
    assert "agent/hermes-codex/glue-110-runbook-05-07-usability" in roadmap
    assert "GLUE-070` through `GLUE-100`" in readme
    assert "GLUE-110" in readme


def test_validation_runbook_explains_invariants_and_uses_exact_local_tools() -> None:
    runbook = (RUNBOOK_ROOT / "05-VALIDATE-AND-RERUN.md").read_text()
    prerequisites = section(
        runbook,
        "## Step 1 — Confirm the reviewed validation prerequisites",
        "## Step 2 — Reconcile source and target",
    )
    reconciliation = section(
        runbook,
        "## Step 2 — Reconcile source and target",
        "## Step 3 — Run the bounded rerun proof",
    )

    assert "O = D" in runbook and "I = A" in runbook
    assert "RUFF=.venv/bin/ruff" in prerequisites
    assert "PYTEST=.venv/bin/pytest" in prerequisites
    assert "unset INSTANCE_ID" in reconciliation
    assert "count" in runbook and "fingerprint" in runbook


def test_destroy_runbook_teaches_the_plan_boundary_and_exact_retry() -> None:
    runbook = (RUNBOOK_ROOT / "06-DESTROY.md").read_text()

    assert "plan is the exact saved instruction set" in runbook
    assert "identity metadata" in runbook
    assert "sleep 30" in runbook
    assert "APPROVE_LAB_DESTROY_VERIFY=1" in runbook
    assert 'EXPECTED_AWS_ACCOUNT="$EXPECTED_AWS_ACCOUNT"' in runbook
    assert 'EXPECTED_ARTIFACT_BUCKET="$EXPECTED_ARTIFACT_BUCKET"' in runbook


def test_troubleshooting_is_standalone_exact_and_uses_state_names() -> None:
    runbook = (RUNBOOK_ROOT / "07-TROUBLESHOOTING.md").read_text()
    first_line = section(
        runbook, "## Step 1 — Run bounded first-line diagnostics", "## Focused failure entries"
    )
    optional = section(runbook, "## Optional — GitHub-to-EC2 write workflow")

    assert "AWS_DEFAULT_REGION" in first_line
    assert "unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY" in first_line
    for output_name in (
        "postgres_glue_connection_name",
        "mongodb_glue_connection_name",
        "glue_job_name",
        "glue_crawler_name",
    ):
        assert output_name in runbook
    assert "APPROVE_LAB_DESTROY_VERIFY=1" in runbook
    assert "sudo -u ec2-user -H" in optional
    assert "stat -c '%a' \"$HOME/" not in optional


def test_runbook_sequence_and_local_markdown_links_are_complete() -> None:
    ordered = [
        "00-PREREQUISITES.md",
        "01-DEPLOY-INFRASTRUCTURE.md",
        "02-START-DATABASES.md",
        "03-CONFIGURE-GLUE.md",
        "04-RUN-MIGRATION.md",
        "05-VALIDATE-AND-RERUN.md",
        "06-DESTROY.md",
    ]
    for current, following in zip(ordered, ordered[1:]):
        assert following in (RUNBOOK_ROOT / current).read_text()

    markdown_files = [ROOT / "README.md", *RUNBOOK_ROOT.glob("*.md")]
    link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for document in markdown_files:
        for target in link_pattern.findall(document.read_text()):
            if target.startswith(("http://", "https://", "#")):
                continue
            relative_path = target.split("#", 1)[0]
            assert (document.parent / relative_path).resolve().exists(), (
                f"{document.relative_to(ROOT)} has broken link {target}"
            )


def test_all_runbooks_use_the_canonical_profile_and_user_run_boundary() -> None:
    combined = "\n".join(path.read_text() for path in RUNBOOK_ROOT.glob("*.md"))

    assert "personal-lab" not in combined
    for path in sorted(RUNBOOK_ROOT.glob("[0-9][0-9]-*.md")):
        assert "User-run only" in path.read_text(), path.name
