from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def section(document: str, start: str, end: str | None = None) -> str:
    body = document.split(start, 1)[1]
    return body if end is None else body.split(end, 1)[0]


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o700)


def test_ssm_bootstrap_surfaces_remote_evidence_with_mocked_boundaries(
    tmp_path: Path,
) -> None:
    fake_aws = tmp_path / "aws"
    fake_terraform = tmp_path / "terraform"
    write_executable(
        fake_aws,
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
query = args[args.index("--query") + 1] if "--query" in args else ""
if "sts" in args and "get-caller-identity" in args:
    print("test-account")
elif "ssm" in args and "send-command" in args:
    print("test-command-id")
elif "ssm" in args and "get-command-invocation" in args and query == "Status":
    print("Success")
elif "ssm" in args and "get-command-invocation" in args:
    print('{"Status":"Success","Output":"remote assertions: PASS","Error":""}')
else:
    raise SystemExit(f"unexpected aws arguments: {args}")
""",
    )
    write_executable(
        fake_terraform,
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
name = args[-1]
values = {
    "aws_account_id": "test-account",
    "aws_region": "us-east-1",
    "database_instance_id": "i-test",
}
print(values[name])
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "AWS_CLI": str(fake_aws),
            "AWS_PROFILE": "personal-test",
            "AWS_REGION": "us-east-1",
            "TERRAFORM": str(fake_terraform),
        }
    )

    result = subprocess.run(
        [str(ROOT / "scripts/run-ssm-bootstrap.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert '"Status":"Success"' in result.stdout
    assert "remote assertions: PASS" in result.stdout
    assert "SSM bootstrap: PASS (command_id=test-command-id)" in result.stdout


def test_database_restart_and_reset_steps_are_cleanup_safe() -> None:
    runbook = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()
    restart = section(
        runbook,
        "### Step 5 — Verify a non-destructive restart",
        "### Step 6 — Reset and deterministically reseed the disposable data layer",
    )
    reset = section(
        runbook,
        "### Step 6 — Reset and deterministically reseed the disposable data layer",
        "## Optional — Run the data layer on the Mac",
    )

    for step in (restart, reset):
        assert "set -euo pipefail" in step
        assert "trap 'rm -f .env' EXIT" in step
        assert "make local-status" in step
        assert "test ! -e .env" in step
        assert "docker ps --filter label=com.docker.compose.project=" in step
    assert "export RESET_VOLUMES=1" not in reset
    assert "make local-down RESET_VOLUMES=1" in reset


def test_optional_local_path_refuses_to_overwrite_an_environment_file() -> None:
    runbook = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()
    local_path = section(runbook, "### Step M1 — Generate local credentials")

    assert "test ! -e .env" in local_path
    assert "install -m 600 .env.example .env" in local_path
    assert "cp .env.example .env" not in local_path


def test_beginner_paths_have_current_profile_and_ssm_guidance() -> None:
    standard = (ROOT / "docs/project/DOCUMENTATION_STANDARD.md").read_text()
    deploy = (ROOT / "docs/runbook/01-DEPLOY-INFRASTRUCTURE.md").read_text()
    databases = (ROOT / "docs/runbook/02-START-DATABASES.md").read_text()

    assert "personal-lab" not in standard
    assert "only after `GLUE-025`" not in databases
    for expected in (
        "key_command_id=",
        "configure_command_id=",
        "aws ssm wait command-executed",
        "aws ssm get-command-invocation",
    ):
        assert expected in deploy


def test_roadmap_tracks_the_bounded_glue_090_task() -> None:
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text()

    assert "| `GLUE-090` | IN PROGRESS |" in roadmap
    assert "agent/hermes-codex/glue-090-runbook-01-02-usability" in roadmap
    assert "Make runbooks 01–02 executable and beginner-safe" in roadmap
