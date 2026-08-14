from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

RUNBOOKS = [
    "README.md",
    "00-PREREQUISITES.md",
    "01-DEPLOY-INFRASTRUCTURE.md",
    "02-START-DATABASES.md",
    "03-CONFIGURE-GLUE.md",
    "04-RUN-MIGRATION.md",
    "05-VALIDATE-AND-RERUN.md",
    "06-DESTROY.md",
    "07-TROUBLESHOOTING.md",
]

UNIMPLEMENTED_TARGETS = {
    "validate": "GLUE-050",
    "rerun-test": "GLUE-050",
    "cost-check": "GLUE-060",
}


def run_make(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_readme_is_a_navigation_page_for_the_complete_sequence() -> None:
    readme = (ROOT / "README.md").read_text()

    for heading in (
        "## Objective",
        "## Architecture",
        "## What this lab creates",
        "## Time and cost",
        "## Primary sequence",
        "## Prerequisites summary",
        "## Runbooks",
        "## Current status",
    ):
        assert heading in readme

    sequence = readme.split("## Primary sequence", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    assert re.findall(r"^\d+\.", sequence, flags=re.MULTILINE) == [
        f"{number}." for number in range(1, 11)
    ]
    for runbook in RUNBOOKS:
        assert f"docs/runbook/{runbook}" in readme
    assert "> [!WARNING]" in readme
    assert "make destroy-lab" in readme


def test_runtime_metadata_matches_aws_glue_5_1_baseline() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert metadata["project"]["requires-python"] == ">=3.11,<3.12"
    assert (ROOT / ".java-version").read_text().strip() == "17"
    assert (ROOT / "requirements/runtime.txt").read_text().splitlines() == ["pyspark==3.5.6"]


def test_environment_example_contains_only_safe_nonsecret_inputs() -> None:
    lines = [
        line
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    values = dict(line.split("=", 1) for line in lines)

    assert values == {
        "AWS_PROFILE": "your-personal-aws-profile",
        "AWS_REGION": "us-east-1",
        "DATABASE_BIND_ADDRESS": "127.0.0.1",
        "POSTGRES_DB": "sales_lab",
        "POSTGRES_USER": "lab_admin",
        "POSTGRES_PASSWORD": "",
        "MONGO_INITDB_ROOT_USERNAME": "lab_root",
        "MONGO_INITDB_ROOT_PASSWORD": "",
        "MONGO_DATABASE": "migration_lab",
        "MONGO_GLUE_USERNAME": "glue_writer",
        "MONGO_GLUE_PASSWORD": "",
    }
    assert all("://" not in value for value in values.values())


@pytest.mark.parametrize(("target", "owner"), UNIMPLEMENTED_TARGETS.items())
def test_future_make_target_fails_with_roadmap_owner(target: str, owner: str) -> None:
    result = run_make(target)

    assert result.returncode != 0
    assert (
        f"ERROR: make {target} is not implemented; owned by roadmap task {owner}." in result.stderr
    )


def test_design_blueprint_directories_and_current_components_exist() -> None:
    expected_directories = [
        "docker/mongodb/init",
        "docker/postgres/init",
        "infrastructure/terraform",
        "scripts",
        "glue/jobs",
        "src/glue_lab",
        "tests/integration",
        "validation",
    ]
    for relative_path in expected_directories:
        assert (ROOT / relative_path).is_dir()

    current_files = [
        "glue/jobs/postgres_orders_to_mongodb.py",
        "src/glue_lab/transformations.py",
    ]
    for relative_path in current_files:
        assert (ROOT / relative_path).is_file()

    future_files = [
        "src/glue_lab/validation.py",
        "validation/reconcile.py",
    ]
    for relative_path in future_files:
        assert not (ROOT / relative_path).exists()


def test_roadmap_records_merged_foundation_and_grouped_glue_work() -> None:
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()

    for task, pr in (("GLUE-000", 1), ("GLUE-010", 2), ("GLUE-020", 3), ("GLUE-025", 4)):
        assert (
            f"| `{task}` | DONE | "
            f"[#{pr}](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/{pr}) |"
        ) in roadmap
    assert "MERGED — PENDING LIVE VALIDATION" not in roadmap
    for task in ("GLUE-030", "GLUE-040"):
        assert f"| `{task}` | IN PROGRESS | PR #5 PLACEHOLDER |" in roadmap
    for task in ("GLUE-050", "GLUE-060"):
        assert f"| `{task}` | NOT STARTED |" in roadmap


def test_governance_separates_local_command_proof_from_optional_user_run_evidence() -> None:
    acceptance = (ROOT / "docs/project/ACCEPTANCE_CRITERIA.md").read_text()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()

    assert "credential-free command-contract execution" in acceptance
    assert "APPROVE_LAB_APPLY=1 make infra-apply" in acceptance
    assert "APPROVE_LAB_DESTROY=1 make destroy-lab" in acceptance
    glue_060 = roadmap.split("## `GLUE-060`", maxsplit=1)[1]
    assert "optional user-run release evidence" in glue_060
    assert "- Full E2E run passes." not in glue_060
    assert "- `terraform destroy` succeeds." not in glue_060
