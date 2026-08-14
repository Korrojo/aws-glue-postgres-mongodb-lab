from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "aws-glue-postgres-mongodb-lab"


def run_make(
    *arguments: str,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o700)


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
    assert '"operation": "destroy"' in plan_script
    assert "apply -input=false destroy.tfplan" in destroy_script
    assert "terraform destroy" not in destroy_script
    assert '[[ "${APPROVE_LAB_DESTROY:-0}" != "1" ]]' in destroy_script
    assert 'identity["Arn"] == metadata.get("principal_arn")' in destroy_script
    assert 'apply_attempted="1"' in destroy_script
    assert '[[ "$apply_attempted" == "1" ]]' in destroy_script
    assert '"$terraform_bin" -chdir="$tf_root" state list' in destroy_script
    assert "destroy verification: PASS" in destroy_script


def test_destroy_lifecycle_rejects_ambient_credentials_and_consumes_only_saved_plan(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / PROJECT
    shutil.copytree(
        ROOT,
        repo_root,
        ignore=shutil.ignore_patterns(
            ".git",
            ".terraform",
            ".pytest_cache",
            "__pycache__",
            "terraform.tfstate",
            "destroy.tfplan",
            ".destroy.tfplan.identity.json",
        ),
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_aws = fake_bin / "aws"
    fake_terraform = fake_bin / "terraform"
    state_json = tmp_path / "state.json"
    apply_marker = tmp_path / "applied"
    terraform_log = tmp_path / "terraform.log"
    state_file = repo_root / "infrastructure/terraform/terraform.tfstate"
    plan_file = repo_root / "infrastructure/terraform/destroy.tfplan"
    metadata_file = repo_root / "infrastructure/terraform/.destroy.tfplan.identity.json"

    state_payload = json.dumps(
        {
            "lineage": "test-lineage",
            "serial": 7,
            "outputs": {
                "aws_region": {"value": "us-east-1"},
                "aws_account_id": {"value": "test-account"},
            },
        }
    )
    state_json.write_text(state_payload)
    state_file.write_text(state_payload)
    write_executable(
        fake_git,
        """#!/usr/bin/env python3
import os
import sys
args = sys.argv[1:]
if args[-2:] == ["rev-parse", "--show-toplevel"]:
    print(os.environ["FAKE_REPO_ROOT"])
elif args[-2:] == ["status", "--short"]:
    pass
elif args[-2:] == ["rev-parse", "HEAD"]:
    print("a" * 40)
else:
    raise SystemExit(f"unexpected git arguments: {args}")
""",
    )
    write_executable(
        fake_aws,
        """#!/usr/bin/env python3
import json
import sys
args = sys.argv[1:]
if "sts" in args and "get-caller-identity" in args:
    if "--query" in args and args[args.index("--query") + 1] == "Account":
        print("test-account")
    else:
        print(json.dumps({"Account": "test-account", "Arn": "test-principal"}))
elif args[:2] in (
    ["resourcegroupstaggingapi", "get-resources"],
    ["ec2", "describe-instances"],
    ["ec2", "describe-vpc-endpoints"],
    ["s3api", "list-buckets"],
):
    print("0")
elif args and args[0] == "glue":
    print("EntityNotFoundException", file=sys.stderr)
    raise SystemExit(255)
elif args[:2] == ["secretsmanager", "describe-secret"]:
    print("ResourceNotFoundException", file=sys.stderr)
    raise SystemExit(255)
elif args[:2] == ["iam", "get-role"]:
    print("NoSuchEntity", file=sys.stderr)
    raise SystemExit(255)
else:
    raise SystemExit(f"unexpected aws arguments: {args}")
""",
    )
    write_executable(
        fake_terraform,
        """#!/usr/bin/env python3
import os
import pathlib
import sys
args = sys.argv[1:]
log = pathlib.Path(os.environ["FAKE_TERRAFORM_LOG"])
with log.open("a") as handle:
    handle.write(" ".join(args) + "\\n")
command_index = 1 if args and args[0].startswith("-chdir=") else 0
command = args[command_index]
if command == "workspace" and args[command_index + 1] == "show":
    print(os.environ.get("FAKE_WORKSPACE", "default"))
elif command == "state" and args[command_index + 1] == "pull":
    print(pathlib.Path(os.environ["FAKE_STATE_JSON"]).read_text())
elif command == "state" and args[command_index + 1] == "list":
    if not pathlib.Path(os.environ["FAKE_APPLY_MARKER"]).exists():
        print("aws_vpc.lab")
elif (
    command == "output"
    and args[command_index + 1 : command_index + 3]
    == ["-raw", "artifact_bucket_name"]
):
    print("test-artifact-bucket")
elif command == "plan":
    pathlib.Path(os.environ["FAKE_PLAN_FILE"]).write_bytes(b"reviewed-destroy-plan")
elif command == "apply":
    pathlib.Path(os.environ["FAKE_APPLY_MARKER"]).touch()
    if os.environ.get("FAKE_APPLY_FAIL") == "1":
        raise SystemExit(7)
else:
    raise SystemExit(f"unexpected terraform arguments: {args}")
""",
    )

    env = os.environ.copy()
    for variable_name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
        "AWS_ROLE_SESSION_NAME",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_CONTAINER_AUTHORIZATION_TOKEN",
        "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
        "TF_WORKSPACE",
        "TF_DATA_DIR",
        "TF_CLI_ARGS",
        "TF_CLI_ARGS_plan",
        "TF_CLI_ARGS_apply",
    ):
        env.pop(variable_name, None)
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
            "AWS_PROFILE": "personal-test",
            "AWS_REGION": "us-east-1",
            "AWS_CLI": str(fake_aws),
            "TERRAFORM": str(fake_terraform),
            "FAKE_REPO_ROOT": str(repo_root),
            "FAKE_STATE_JSON": str(state_json),
            "FAKE_APPLY_MARKER": str(apply_marker),
            "FAKE_PLAN_FILE": str(plan_file),
            "FAKE_TERRAFORM_LOG": str(terraform_log),
        }
    )

    for path in (plan_file, metadata_file, apply_marker, terraform_log):
        path.unlink(missing_ok=True)

    for variable_name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "TF_WORKSPACE",
        "TF_CLI_ARGS_plan",
    ):
        terraform_log.unlink(missing_ok=True)
        rejected = run_make(
            "destroy-plan",
            env=env | {variable_name: "must-not-be-used"},
            cwd=repo_root,
        )
        assert rejected.returncode != 0
        assert "ambient AWS or Terraform override variables" in rejected.stderr
        assert not terraform_log.exists()

    terraform_log.unlink(missing_ok=True)
    wrong_workspace = run_make(
        "destroy-plan",
        env=env | {"FAKE_WORKSPACE": "other"},
        cwd=repo_root,
    )
    assert wrong_workspace.returncode != 0
    assert "Terraform workspace must be default" in wrong_workspace.stderr
    assert not plan_file.exists()

    mismatched_state = json.loads(state_payload)
    mismatched_state["serial"] = 8
    state_file.write_text(json.dumps(mismatched_state))
    mismatched = run_make("destroy-plan", env=env, cwd=repo_root)
    assert mismatched.returncode != 0
    assert "active state serial does not match terraform.tfstate" in mismatched.stderr
    assert not plan_file.exists()
    state_file.write_text(state_payload)

    planned = run_make("destroy-plan", env=env, cwd=repo_root)
    assert planned.returncode == 0, planned.stderr
    metadata = json.loads(metadata_file.read_text())
    assert metadata["operation"] == "destroy"
    assert metadata_file.stat().st_mode & 0o777 == 0o600

    metadata["operation"] = "apply"
    metadata_file.write_text(json.dumps(metadata))
    terraform_log.write_text("")
    rejected_operation = run_make(
        "destroy-lab",
        "APPROVE_LAB_DESTROY=1",
        env=env,
        cwd=repo_root,
    )
    assert rejected_operation.returncode != 0
    assert "operation is not destroy" in rejected_operation.stderr
    assert not apply_marker.exists()
    assert not any(" apply " in f" {line} " for line in terraform_log.read_text().splitlines())

    planned = run_make("destroy-plan", env=env, cwd=repo_root)
    assert planned.returncode == 0, planned.stderr
    destroyed = run_make(
        "destroy-lab",
        "APPROVE_LAB_DESTROY=1",
        env=env,
        cwd=repo_root,
    )
    assert destroyed.returncode == 0, destroyed.stderr
    assert apply_marker.exists()
    assert not plan_file.exists()
    assert not metadata_file.exists()
    apply_lines = [
        line for line in terraform_log.read_text().splitlines() if " apply " in f" {line} "
    ]
    assert len(apply_lines) == 1
    assert apply_lines[0].endswith("apply -input=false destroy.tfplan")

    apply_marker.unlink()
    terraform_log.write_text("")
    planned_again = run_make("destroy-plan", env=env, cwd=repo_root)
    assert planned_again.returncode == 0, planned_again.stderr
    failed = run_make(
        "destroy-lab",
        "APPROVE_LAB_DESTROY=1",
        env=env | {"FAKE_APPLY_FAIL": "1"},
        cwd=repo_root,
    )
    assert failed.returncode != 0
    assert not plan_file.exists()
    assert not metadata_file.exists()


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
    assert "/$project_name/mongodb-glue" in bootstrap_script


def test_foundation_status_and_user_run_only_governance_contract() -> None:
    readme = (ROOT / "README.md").read_text()
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()
    deploy_runbook = (ROOT / "docs/runbook/01-DEPLOY-INFRASTRUCTURE.md").read_text()
    database_runbook = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()
    destroy_runbook = (ROOT / "docs/runbook/06-DESTROY.md").read_text()

    assert "MERGED — PENDING LIVE VALIDATION" not in readme
    assert "MERGED — PENDING LIVE VALIDATION" not in roadmap
    assert "| `GLUE-020` | DONE |" in roadmap
    assert "| `GLUE-025` | DONE |" in roadmap
    for task in ("GLUE-030", "GLUE-040"):
        assert f"| `{task}` | DONE | [#5]" in roadmap
    for task in ("GLUE-050", "GLUE-060"):
        assert f"| `{task}` | IN PROGRESS | PR #6 PLACEHOLDER |" in roadmap

    combined_foundation_docs = deploy_runbook + database_runbook + destroy_runbook
    assert "User-run only" in combined_foundation_docs
    assert "Agents must never request or use AWS credentials" in combined_foundation_docs
    assert "separate issue/PR" in combined_foundation_docs
    assert "No agent-run live AWS evidence is required" in combined_foundation_docs
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

    assert "Status: implementation complete" in destroy_runbook
    assert "GLUE-060" in destroy_runbook
    assert "post-destroy known-service verification: PASS" in destroy_runbook
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
