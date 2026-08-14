from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "aws-glue-postgres-mongodb-lab"


def load_reconcile():
    spec = importlib.util.spec_from_file_location(
        "reconcile_under_test", ROOT / "validation/reconcile.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reconcile_entrypoint_keeps_database_credentials_off_argv_and_output(tmp_path) -> None:
    module = load_reconcile()
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(arguments, **kwargs):
        calls.append((list(arguments), kwargs.get("input")))
        if "ps" in arguments:
            return subprocess.CompletedProcess(arguments, 0, "container-id\n", "")
        if "inspect" in arguments:
            service = "postgres" if len(calls) == 2 else "mongodb"
            return subprocess.CompletedProcess(arguments, 0, f"/{PROJECT}-{service}-1\n", "")
        if any("psql" in argument for argument in arguments):
            return subprocess.CompletedProcess(
                arguments,
                0,
                json.dumps(
                    {
                        "active_order_count": 0,
                        "active_item_count": 0,
                        "deleted_order_count": 0,
                        "deleted_item_count": 0,
                        "orders": [],
                        "deleted_order_ids": [],
                        "deleted_item_ids": [],
                    }
                )
                + "\n",
                "",
            )
        return subprocess.CompletedProcess(
            arguments,
            0,
            '{"target_document_count":0,"target_item_count":0,"documents":[]}\n',
            "",
        )

    postgres = {
        "host": "private.invalid",
        "port": 5432,
        "database": "sales_lab",
        "username": "postgres-user-sentinel",
        "password": "postgres-password-sentinel",
    }
    mongodb = {
        "host": "private.invalid",
        "port": 27017,
        "database": "migration_lab",
        "username": "mongo-user-sentinel",
        "password": "mongo-password-sentinel",
    }
    postgres_container = module.resolve_container("postgres", run=fake_run)
    mongo_container = module.resolve_container("mongodb", run=fake_run)
    module.read_source(postgres, postgres_container, run=fake_run)
    module.read_target(mongodb, mongo_container, run=fake_run)

    argv_text = "\n".join(" ".join(arguments) for arguments, _ in calls)
    stdin_text = "\n".join(value or "" for _, value in calls)
    for sentinel in (
        "postgres-user-sentinel",
        "postgres-password-sentinel",
        "mongo-user-sentinel",
        "mongo-password-sentinel",
    ):
        assert sentinel not in argv_text
        assert sentinel in stdin_text
    assert f"/{PROJECT}-postgres-1" not in argv_text
    assert "docker exec -i" not in stdin_text


def test_reconcile_main_writes_private_redacted_artifact_and_fails_on_mismatch(
    tmp_path, monkeypatch, capsys
) -> None:
    module = load_reconcile()
    source = {
        "orders": [{"order_id": 7, "items": [], "order_total": "0"}],
        "deleted_order_ids": [],
        "deleted_item_ids": [],
    }
    target = {"documents": []}
    monkeypatch.setattr(module, "load_secret", lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "resolve_container", lambda service, **kwargs: service)
    monkeypatch.setattr(module, "read_source", lambda *args, **kwargs: source)
    monkeypatch.setattr(module, "read_target", lambda *args, **kwargs: target)
    output = tmp_path / "private" / "result.json"

    return_code = module.main(["--output", str(output)])

    assert return_code == 1
    assert output.stat().st_mode & 0o777 == 0o600
    artifact = json.loads(output.read_text())
    assert artifact["passed"] is False
    assert artifact["mismatch_categories"]["missing_target_key"] == 1
    console = capsys.readouterr().out
    assert json.loads(console) == artifact
    assert "private.invalid" not in console
    assert "order_id" not in console


def test_reconcile_boundary_rejects_unbounded_or_wrong_secret_shapes() -> None:
    module = load_reconcile()
    with pytest.raises(module.BoundaryError, match="secret schema"):
        module.validate_secret({"username": "u", "password": "p"}, "postgres")
    with pytest.raises(module.BoundaryError, match="bounded"):
        module.validate_source_payload(
            {
                "active_order_count": 101,
                "active_item_count": 0,
                "deleted_order_count": 0,
                "deleted_item_count": 0,
                "orders": [],
                "deleted_order_ids": [],
                "deleted_item_ids": [],
            }
        )


def test_operational_scripts_are_approval_gated_bounded_and_exactly_scoped() -> None:
    makefile = (ROOT / "Makefile").read_text()
    validate = (ROOT / "scripts/run-validation.sh").read_text()
    rerun = (ROOT / "scripts/run-rerun-test.sh").read_text()
    cost = (ROOT / "scripts/cost-check.sh").read_text()
    ssm = (ROOT / "scripts/lib/user-run-ssm.sh").read_text()
    remote = (ROOT / "validation/rerun.py").read_text()

    for target, script, approval in (
        ("validate", validate, "APPROVE_GLUE_VALIDATE"),
        ("rerun-test", rerun, "APPROVE_GLUE_RERUN"),
        ("cost-check", cost, "APPROVE_LAB_COST_CHECK"),
    ):
        assert f"{target}: ## USER-RUN ONLY" in makefile
        assert script.startswith("#!/usr/bin/env bash\nset -euo pipefail")
        assert "user-run-aws-guard.sh" in script
        assert f"require_user_run_aws {approval}" in script
        assert approval in makefile

    assert "SSM_TIMEOUT_SECONDS" in ssm
    assert "<= 1800" in ssm
    assert "remaining_seconds" in ssm
    assert "sleep_seconds" in ssm
    assert "expected_git_sha" in ssm
    assert "git -C /opt/aws-glue-postgres-mongodb-lab status --short" in ssm
    assert "git -C /opt/aws-glue-postgres-mongodb-lab rev-parse HEAD" in ssm
    assert "user-run SSM command: PASS" in ssm
    for phase in (
        "unchanged_second_run",
        "controlled_replacement",
        "stale_target_detection",
        "targeted_stale_resolution",
        "reset",
    ):
        assert phase in rerun
    assert "APPROVE_GLUE_RUN=1" in rerun
    assert "1001" in remote and "1003" in remote
    assert "deleteOne({{_id:1003}})" in remote.replace(" ", "")
    assert "deleteMany" not in remote
    assert "TRUNCATE" not in remote.upper()
    assert "DROP " not in remote.upper()


def test_missing_operational_approval_fails_before_any_aws_call(tmp_path) -> None:
    fake_aws = tmp_path / "aws"
    aws_log = tmp_path / "aws.log"
    fake_aws.write_text("#!/usr/bin/env bash\nprintf '%s\\n' called >>\"$FAKE_AWS_LOG\"\nexit 99\n")
    fake_aws.chmod(0o700)
    env = os.environ.copy()
    env.update(
        {
            "AWS_CLI": str(fake_aws),
            "FAKE_AWS_LOG": str(aws_log),
            "AWS_PROFILE": "personal-test",
            "AWS_REGION": "us-east-1",
        }
    )
    for variable in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_ENDPOINT_URL",
    ):
        env.pop(variable, None)

    for relative, approval in (
        ("scripts/run-validation.sh", "APPROVE_GLUE_VALIDATE"),
        ("scripts/run-rerun-test.sh", "APPROVE_GLUE_RERUN"),
        ("scripts/cost-check.sh", "APPROVE_LAB_COST_CHECK"),
    ):
        result = subprocess.run(
            [str(ROOT / relative)],
            cwd=ROOT,
            env=env | {approval: "0"},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert approval in result.stderr
        assert not aws_log.exists()


def test_validate_script_succeeds_with_fake_terraform_aws_and_ssm_boundaries(
    tmp_path,
) -> None:
    repo = tmp_path / PROJECT
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(".git", ".terraform", "terraform.tfstate"),
    )
    (repo / "infrastructure/terraform/terraform.tfstate").write_text("{}")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_terraform = fake_bin / "terraform"
    fake_aws = fake_bin / "aws"
    aws_log = tmp_path / "aws.log"
    for path, content in (
        (
            fake_git,
            """#!/usr/bin/env python3
import os
import sys
args = sys.argv[1:]
if args[-2:] == ["rev-parse", "--show-toplevel"]:
    print(os.environ["FAKE_REPO"])
elif args[-2:] == ["rev-parse", "HEAD"]:
    print("a" * 40)
elif args[-2:] == ["status", "--short"]:
    pass
else:
    raise SystemExit(f"unexpected git arguments: {args}")
""",
        ),
        (
            fake_terraform,
            """#!/usr/bin/env python3
import sys
args = sys.argv[1:]
command = args[1] if args[0].startswith("-chdir=") else args[0]
if command == "workspace":
    print("default")
elif command == "output":
    values = {
        "aws_region": "us-east-1",
        "aws_account_id": "test-account",
        "database_instance_id": "test-instance",
    }
    print(values[args[-1]])
else:
    raise SystemExit(f"unexpected terraform arguments: {args}")
""",
        ),
        (
            fake_aws,
            """#!/usr/bin/env python3
import os
import pathlib
import sys
args = sys.argv[1:]
with pathlib.Path(os.environ["FAKE_AWS_LOG"]).open("a") as handle:
    handle.write(" ".join(args) + "\\n")
if "sts" in args:
    print("test-account")
elif args[:2] == ["ssm", "send-command"]:
    print("test-command")
elif args[:2] == ["ssm", "get-command-invocation"]:
    query = args[args.index("--query") + 1]
    if query == "Status":
        print("Success")
    else:
        print('{"schema_version":1,"passed":true,"counts":{},"mismatch_categories":{},"mismatch_count":0}')
else:
    raise SystemExit(f"unexpected aws arguments: {args}")
""",
        ),
    ):
        path.write_text(content)
        path.chmod(0o700)

    env = os.environ.copy()
    for name in (
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
        "AWS_ENDPOINT_URL",
        "AWS_ENDPOINT_URL_SSM",
        "TF_WORKSPACE",
        "TF_DATA_DIR",
        "TF_CLI_ARGS",
    ):
        env.pop(name, None)
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
            "AWS_PROFILE": "personal-test",
            "AWS_REGION": "us-east-1",
            "AWS_CLI": str(fake_aws),
            "TERRAFORM": str(fake_terraform),
            "APPROVE_GLUE_VALIDATE": "1",
            "FAKE_REPO": str(repo),
            "FAKE_AWS_LOG": str(aws_log),
        }
    )
    result = subprocess.run(
        [str(repo / "scripts/run-validation.sh")],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"passed":true' in result.stdout
    assert "validate: PASS" in result.stdout
    assert "test-account" not in result.stdout + result.stderr
    assert "test-instance" not in result.stdout + result.stderr

    aws_log.unlink()
    rejected = subprocess.run(
        [str(repo / "scripts/run-validation.sh")],
        cwd=repo,
        env=env | {"AWS_ENDPOINT_URL_SSM": ""},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "endpoint override" in rejected.stderr.lower()
    assert not aws_log.exists()


def test_destroy_verification_is_read_only_known_service_and_consumed_plan_integrated() -> None:
    verify = (ROOT / "scripts/verify-destroyed.sh").read_text()
    destroy = (ROOT / "scripts/terraform-destroy.sh").read_text()

    assert verify.startswith("#!/usr/bin/env bash\nset -euo pipefail")
    assert "APPROVE_LAB_DESTROY_VERIFY" in verify
    assert "EXPECTED_AWS_ACCOUNT" in verify
    assert "AWS_ENDPOINT_URL" in verify
    assert "resourcegroupstaggingapi get-resources" in verify
    for service_check in (
        "ec2 describe-instances",
        "ec2 describe-vpc-endpoints",
        "glue get-job",
        "glue get-crawler",
        "glue get-connection",
        "glue get-database",
        "secretsmanager describe-secret",
        "iam get-role",
        "s3api list-buckets",
    ):
        assert service_check in verify
    for mutation in (
        "delete-",
        "terminate-instances",
        "stop-instances",
        "remove-from-state",
    ):
        assert mutation not in verify
    assert "apply -input=false destroy.tfplan" in destroy
    assert destroy.index("apply -input=false destroy.tfplan") < destroy.index(
        "scripts/verify-destroyed.sh"
    )
    assert "plan -destroy" not in destroy


def test_release_runbooks_and_status_have_no_owned_deferred_markers() -> None:
    road = (ROOT / "docs/project/ROADMAP.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for task in ("GLUE-050", "GLUE-060"):
        assert f"| `{task}` | DONE | [#6]" in road
    assert "PR #6 PLACEHOLDER" not in road
    assert "PR #6 PLACEHOLDER" not in readme
    assert "[PR #6](https://github.com/Korrojo/aws-glue-postgres-mongodb-lab/pull/6)" in readme
    for name in (
        "05-VALIDATE-AND-RERUN.md",
        "06-DESTROY.md",
        "07-TROUBLESHOOTING.md",
    ):
        runbook = (ROOT / "docs/runbook" / name).read_text()
        assert "User-run only" in runbook
        assert "template until implementation" not in runbook
        assert "explicitly deferred" not in runbook
        for field in (
            "**Purpose**",
            "**Run from**",
            "**Prerequisites**",
            "**Inputs**",
            "**Command",
            "**Expected result**",
            "**Verify",
            "**Repeat, reset, or rollback**",
            "**If it fails**",
            "**Next**",
        ):
            assert field in runbook
    optional = (ROOT / "docs/runbook/07-TROUBLESHOOTING.md").read_text()
    assert "Optional — GitHub-to-EC2 write workflow" in optional
    assert "not required for the core lab" in optional
