from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF_ROOT = ROOT / "infrastructure/terraform"


def terraform_text() -> str:
    return "\n".join(path.read_text() for path in sorted(TF_ROOT.glob("*.tf")))


def resource_types() -> list[str]:
    return re.findall(r'^resource\s+"([^"]+)"\s+"[^"]+"', terraform_text(), re.MULTILINE)


def test_terraform_root_is_small_locked_and_local_state_only() -> None:
    expected_files = {
        ".terraform.lock.hcl",
        "main.tf",
        "outputs.tf",
        "user_data.sh.tftpl",
        "variables.tf",
        "versions.tf",
    }
    assert expected_files <= {path.name for path in TF_ROOT.iterdir() if path.is_file()}

    text = terraform_text()
    assert 'required_version = ">= 1.15.0, < 2.0.0"' in text
    assert 'version = "~> 6.60"' in text
    assert 'version = "~> 3.9"' in text
    assert 'backend "' not in text
    assert 'module "' not in text


def test_foundation_has_one_lab_path_and_no_forbidden_enterprise_components() -> None:
    types = resource_types()

    assert types.count("aws_vpc") == 1
    assert types.count("aws_subnet") == 1
    assert types.count("aws_internet_gateway") == 1
    assert types.count("aws_route_table") == 1
    assert types.count("aws_route_table_association") == 1
    assert types.count("aws_vpc_endpoint") == 2
    assert types.count("aws_instance") == 1
    assert types.count("aws_s3_bucket") == 1
    assert types.count("aws_secretsmanager_secret") == 2
    assert "aws_nat_gateway" not in types
    assert "aws_eip" not in types
    assert "aws_lb" not in types
    assert "aws_autoscaling_group" not in types
    assert "aws_secretsmanager_secret_version" not in types


def test_network_rules_allow_only_glue_to_reach_database_ports() -> None:
    text = terraform_text()
    types = resource_types()

    for name in ("glue", "database-host", "endpoint"):
        assert re.search(rf'name\s*=\s*"{name}"', text)
    assert len(re.findall(r"from_port\s*=\s*5432", text)) == 1
    assert len(re.findall(r"from_port\s*=\s*27017", text)) == 1
    assert (
        len(
            re.findall(
                r"referenced_security_group_id\s*=\s*aws_security_group\.glue\.id",
                text,
            )
        )
        >= 3
    )
    assert not re.search(r"from_port\s*=\s*22", text)
    assert types.count("aws_vpc_security_group_ingress_rule") == 5
    assert "ingress {" not in text
    assert "cidr_ipv4" not in text
    assert "cidr_ipv6" not in text
    assert "self-referencing All TCP" in text


def test_every_supported_resource_gets_the_required_lab_tags() -> None:
    text = terraform_text()

    for tag in (
        'Project     = "aws-glue-postgres-mongodb-lab"',
        'Environment = "lab"',
        'ManagedBy   = "terraform"',
    ):
        assert tag in text
    assert "default_tags" in text


def test_storage_secrets_iam_and_ec2_follow_the_design() -> None:
    text = terraform_text()
    user_data = (TF_ROOT / "user_data.sh.tftpl").read_text()

    for required in (
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_iam_instance_profile",
        "AmazonSSMManagedInstanceCore",
        "associate_public_ip_address = true",
        'instance_type               = "t3.medium"',
        "encrypted   = true",
        'volume_type = "gp3"',
        "user_data_replace_on_change = true",
    ):
        assert required in text

    for action in (
        "ec2:CreateNetworkInterface",
        "ec2:DeleteNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "cloudwatch:PutMetricData",
        "s3:GetBucketLocation",
        "s3:GetBucketAcl",
    ):
        assert action in text
    assert "AWSGlueServiceRole" not in text
    assert '"glue:*"' not in text
    assert 'variable = "cloudwatch:namespace"' in text
    assert 'values   = ["Glue"]' in text

    assert re.search(r'name\s*=\s*"/\$\{local\.project_name\}/postgres"', text)
    assert re.search(r'name\s*=\s*"/\$\{local\.project_name\}/mongodb"', text)
    assert "secret_string" not in text

    for required in (
        "set -euo pipefail",
        "dnf install -y docker git make python3",
        "systemctl enable --now docker",
        'git clone --branch "${repository_ref}"',
        "/opt/aws-glue-postgres-mongodb-lab",
        "rev-parse HEAD",
        "bootstrap-complete",
    ):
        assert required in user_data
    assert "dnf install -y curl" not in user_data


def test_glue_020_scripts_are_strict_scoped_and_nonsecret() -> None:
    expected = {
        "bootstrap-ec2.sh",
        "configure-ec2-github-write.sh",
        "put-lab-secrets.sh",
        "run-ssm-bootstrap.sh",
        "terraform-apply.sh",
        "terraform-plan.sh",
    }
    scripts = ROOT / "scripts"
    assert expected <= {path.name for path in scripts.iterdir() if path.is_file()}

    for name in expected:
        content = (scripts / name).read_text()
        assert "set -euo pipefail" in content
        assert "aws-glue-postgres-mongodb-lab" in content
        assert "printenv" not in content
        assert "set -x" not in content

    secret_script = (scripts / "put-lab-secrets.sh").read_text()
    assert "secrets.token_hex" in secret_script
    assert "put-secret-value" in secret_script
    assert "SecretString" not in secret_script
    assert "get-caller-identity" in secret_script
    assert "aws_account_id" in secret_script
    assert "does not match Terraform state" in secret_script

    plan_script = (scripts / "terraform-plan.sh").read_text()
    apply_script = (scripts / "terraform-apply.sh").read_text()
    for content in (plan_script, apply_script):
        assert "get-caller-identity" in content
        assert "AWS_PROFILE" in content
        assert "plan_sha256" in content
        assert "git_sha" in content
    assert "account does not match the reviewed plan" in apply_script

    bootstrap_script = (scripts / "bootstrap-ec2.sh").read_text()
    assert 'rm -f "$env_file"' in bootstrap_script

    ssm_script = (scripts / "run-ssm-bootstrap.sh").read_text()
    assert "ssm wait command-executed" not in ssm_script
    assert "deadline=" in ssm_script
    assert "sleep 10" in ssm_script

    deploy_key_script = (scripts / "configure-ec2-github-write.sh").read_text()
    assert "ssh-keygen -t ed25519" in deploy_key_script
    assert "id_ed25519.pub" in deploy_key_script
    assert "core.sshCommand" in deploy_key_script
    assert "known_hosts" in deploy_key_script
    assert 'cat "$private_key"' not in deploy_key_script
    assert "git push origin main" not in deploy_key_script


def test_make_ci_and_runbooks_own_the_glue_020_workflow() -> None:
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    for target in (
        "doctor",
        "infra-init",
        "infra-plan",
        "infra-apply",
        "secrets-put",
        "ec2-bootstrap",
    ):
        assert f"{target}:" in makefile
    assert "doctor infra-init infra-plan infra-apply secrets-put ec2-bootstrap:" not in makefile
    assert "Terraform AWS foundation tests" in workflow
    assert "terraform test" in workflow
    assert "./scripts/terraform-plan.sh" in makefile
    assert "./scripts/terraform-apply.sh" in makefile

    prerequisites = (ROOT / "docs/runbook/00-PREREQUISITES.md").read_text()
    infrastructure = (ROOT / "docs/runbook/01-DEPLOY-INFRASTRUCTURE.md").read_text()
    assert "Status: implemented by `GLUE-020`" in prerequisites
    assert "Status: implemented by `GLUE-020`" in infrastructure
    for document in (prerequisites, infrastructure):
        assert "## Required completed sections" not in document
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
            assert field in document


def test_infrastructure_mutation_targets_fail_closed_without_explicit_inputs() -> None:
    plan = subprocess.run(
        ["make", "--no-print-directory", "infra-plan", "AWS_PROFILE=", "AWS_REGION="],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert plan.returncode != 0
    assert "ERROR: AWS_PROFILE is required." in plan.stderr

    apply = subprocess.run(
        ["make", "--no-print-directory", "infra-apply", "APPROVE_LAB_APPLY=0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert apply.returncode != 0
    assert "ERROR: set APPROVE_LAB_APPLY=1" in apply.stderr

    unbound_apply = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "infra-apply",
            "APPROVE_LAB_APPLY=1",
            "AWS_PROFILE=",
            "AWS_REGION=",
            "TERRAFORM=true",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert unbound_apply.returncode != 0
    assert "ERROR: AWS_PROFILE is required." in unbound_apply.stderr
