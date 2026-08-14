from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "aws-glue-postgres-mongodb-lab"


def run_make(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_destroy_targets_are_review_bound_and_fail_closed_before_aws() -> None:
    makefile = (ROOT / "Makefile").read_text()
    plan_script = (ROOT / "scripts/terraform-destroy-plan.sh").read_text()
    destroy_script = (ROOT / "scripts/terraform-destroy.sh").read_text()

    for target in ("destroy-plan", "destroy-lab", "ec2-reset-data"):
        assert f"{target}:" in makefile
        assert f"make {target}" in makefile

    missing_identity = run_make("destroy-plan", "AWS_PROFILE=", "AWS_REGION=", "AWS_CLI=false")
    assert missing_identity.returncode != 0
    assert "ERROR: AWS_PROFILE is required." in missing_identity.stderr

    missing_approval = run_make(
        "destroy-lab",
        "APPROVE_LAB_DESTROY=0",
        "AWS_PROFILE=",
        "AWS_REGION=",
        "AWS_CLI=false",
        "TERRAFORM=false",
    )
    assert missing_approval.returncode != 0
    assert "ERROR: set APPROVE_LAB_DESTROY=1" in missing_approval.stderr

    for content in (plan_script, destroy_script):
        assert "set -euo pipefail" in content
        assert f'project_name="{PROJECT}"' in content
        assert 'git -C "$repo_root" rev-parse --show-toplevel' in content
        assert "terraform.tfstate" in content
        assert "aws_account_id" in content
        assert "aws_region" in content
        assert "state_lineage" in content
        assert "state_serial" in content
        assert "state_resources_sha256" in content
        assert "plan_sha256" in content
        assert "git_sha" in content

    assert "plan -destroy -input=false -out=destroy.tfplan" in plan_script
    assert "apply -input=false destroy.tfplan" in destroy_script
    assert "terraform destroy" not in destroy_script
    assert '[[ "${APPROVE_LAB_DESTROY:-0}" != "1" ]]' in destroy_script
    assert '"$terraform_bin" -chdir="$tf_root" state list' in destroy_script
    assert "destroy verification: PASS" in destroy_script


def test_ec2_secret_rotation_reset_is_exactly_compose_project_scoped() -> None:
    makefile = (ROOT / "Makefile").read_text()
    ssm_script = (ROOT / "scripts/run-ssm-bootstrap.sh").read_text()
    bootstrap_script = (ROOT / "scripts/bootstrap-ec2.sh").read_text()
    secret_script = (ROOT / "scripts/put-lab-secrets.sh").read_text()

    assert 'RESET_DATA="1"' in makefile
    assert "./scripts/run-ssm-bootstrap.sh" in makefile
    assert "$(COMPOSE) down --volumes;" in makefile
    assert "$(COMPOSE) down --volumes --remove-orphans" not in makefile
    assert "database_instance_id" in ssm_script
    assert "aws_account_id" in ssm_script
    assert "aws_region" in ssm_script
    assert "RESET_DATA=1" in ssm_script

    assert 'reset_data="${RESET_DATA:-0}"' in bootstrap_script
    assert "config --format json" in bootstrap_script
    assert f'expected_project = "{PROJECT}"' in bootstrap_script
    assert 'expected_volumes = {"postgres_data", "mongodb_data"}' in bootstrap_script
    assert 'expected_services = {"postgres", "mongodb"}' in bootstrap_script
    assert "make local-down RESET_VOLUMES=1" in bootstrap_script
    assert bootstrap_script.index("secretsmanager get-secret-value") < bootstrap_script.index(
        "make local-down RESET_VOLUMES=1"
    )
    assert bootstrap_script.index("make local-down RESET_VOLUMES=1") < bootstrap_script.index(
        "make local-up"
    )
    assert "make ec2-reset-data" in secret_script
    assert "make ec2-bootstrap alone" in secret_script


def test_glue_025_status_and_personal_account_live_validation_contract() -> None:
    readme = (ROOT / "README.md").read_text()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()
    deploy_runbook = (ROOT / "docs/runbook/01-DEPLOY-INFRASTRUCTURE.md").read_text()
    database_runbook = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()
    destroy_runbook = (ROOT / "docs/runbook/06-DESTROY.md").read_text()

    exact_status = "MERGED — PENDING LIVE VALIDATION"
    assert exact_status in readme
    assert f"| `GLUE-020` | {exact_status} |" in roadmap
    assert "| `GLUE-025` | IN PROGRESS | PR PLACEHOLDER |" in roadmap
    assert "Branch: `agent/hermes-codex/glue-025-foundation-cleanup`" in roadmap
    for task in ("GLUE-030", "GLUE-040", "GLUE-050", "GLUE-060"):
        assert f"| `{task}` | NOT STARTED |" in roadmap

    checklist = [
        "make doctor",
        "make infra-plan",
        "review the saved infrastructure plan",
        "APPROVE_LAB_APPLY=1 make infra-apply",
        "make secrets-put",
        "make ec2-bootstrap",
        "make destroy-plan",
        "review the saved destroy plan",
        "APPROVE_LAB_DESTROY=1 make destroy-lab",
        "confirm Terraform-managed resource removal",
    ]
    combined_foundation_docs = deploy_runbook + destroy_runbook
    positions = [combined_foundation_docs.index(item) for item in checklist]
    assert positions == sorted(positions)
    assert "Do not fabricate evidence" in combined_foundation_docs
    for forbidden_evidence in (
        "AWS account IDs",
        "principal ARNs",
        "instance IDs",
        "public IP addresses",
        "secret values",
        "credentialed connection strings",
    ):
        assert forbidden_evidence in combined_foundation_docs

    assert "make ec2-reset-data" in deploy_runbook
    assert "make ec2-reset-data" in database_runbook
    assert "`make ec2-bootstrap` alone" in deploy_runbook
    assert "`make ec2-bootstrap` alone" in database_runbook

    assert "Status: foundation destroy implemented by `GLUE-025`" in destroy_runbook
    assert "GLUE-060" in destroy_runbook
    assert "deferred" in destroy_runbook.lower()
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
        assert field in destroy_runbook
