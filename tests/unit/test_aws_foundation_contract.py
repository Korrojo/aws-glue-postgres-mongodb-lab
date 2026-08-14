from __future__ import annotations

import re
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
    assert "backend \"" not in text
    assert "module \"" not in text


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

    assert 'name = "glue"' in text
    assert 'name = "database-host"' in text
    assert 'name = "endpoint"' in text
    assert text.count("from_port                    = 5432") == 1
    assert text.count("from_port                    = 27017") == 1
    assert text.count("referenced_security_group_id = aws_security_group.glue.id") >= 3
    assert "from_port                    = 22" not in text
    assert 'cidr_ipv4                    = "0.0.0.0/0"' not in text
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
        "AWSGlueServiceRole",
        "associate_public_ip_address = true",
        'instance_type               = "t3.medium"',
        "encrypted   = true",
        'volume_type = "gp3"',
        "user_data_replace_on_change = true",
    ):
        assert required in text

    assert "/aws-glue-postgres-mongodb-lab/postgres" in text
    assert "/aws-glue-postgres-mongodb-lab/mongodb" in text
    assert "secret_string" not in text

    for required in (
        "set -euo pipefail",
        "dnf install -y docker git",
        "systemctl enable --now docker",
        "git clone --branch main",
        "/opt/aws-glue-postgres-mongodb-lab",
        "git rev-parse HEAD",
        "bootstrap-complete",
    ):
        assert required in user_data


def test_glue_020_scripts_are_strict_scoped_and_nonsecret() -> None:
    expected = {
        "bootstrap-ec2.sh",
        "configure-ec2-github-write.sh",
        "put-lab-secrets.sh",
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

    deploy_key_script = (scripts / "configure-ec2-github-write.sh").read_text()
    assert "ssh-keygen -t ed25519" in deploy_key_script
    assert "id_ed25519.pub" in deploy_key_script
    assert "cat \"$private_key\"" not in deploy_key_script
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
