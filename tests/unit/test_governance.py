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
    "local-up": "GLUE-010",
    "local-status": "GLUE-010",
    "local-test": "GLUE-010",
    "local-down": "GLUE-010",
    "doctor": "GLUE-020",
    "infra-init": "GLUE-020",
    "infra-plan": "GLUE-020",
    "infra-apply": "GLUE-020",
    "secrets-put": "GLUE-020",
    "ec2-bootstrap": "GLUE-020",
    "deploy": "GLUE-030",
    "crawl": "GLUE-030",
    "run": "GLUE-040",
    "validate": "GLUE-050",
    "rerun-test": "GLUE-050",
    "cost-check": "GLUE-060",
    "destroy-lab": "GLUE-060",
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
    assert lines == ["AWS_PROFILE=your-personal-aws-profile", "AWS_REGION=us-east-1"]


@pytest.mark.parametrize(("target", "owner"), UNIMPLEMENTED_TARGETS.items())
def test_future_make_target_fails_with_roadmap_owner(target: str, owner: str) -> None:
    result = run_make(target)

    assert result.returncode != 0
    assert (
        f"ERROR: make {target} is not implemented; owned by roadmap task {owner}." in result.stderr
    )


@pytest.mark.parametrize(
    ("target", "owner"),
    [("compose-check", "GLUE-010"), ("terraform-check", "GLUE-020")],
)
def test_scaffold_validation_fails_explicitly_until_owned_configuration_exists(
    target: str, owner: str
) -> None:
    result = run_make(target)

    assert result.returncode != 0
    assert f"ERROR: make {target} is not implemented; {owner} must add" in result.stderr


def test_design_blueprint_directories_exist_without_future_components() -> None:
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

    future_files = [
        "docker/compose.yaml",
        "glue/jobs/postgres_orders_to_mongodb.py",
        "src/glue_lab/transformations.py",
        "src/glue_lab/validation.py",
        "validation/reconcile.py",
    ]
    for relative_path in future_files:
        assert not (ROOT / relative_path).exists()


def test_roadmap_preserves_only_glue_000_as_active() -> None:
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()

    expected_status = (
        "| `GLUE-000` | PR OPEN | "
        "[#1](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/1) |"
    )
    assert expected_status in roadmap
    for task_number in range(10, 61, 10):
        assert f"| `GLUE-{task_number:03d}` | NOT STARTED |" in roadmap
