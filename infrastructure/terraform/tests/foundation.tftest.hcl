mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }
}

mock_provider "random" {
  mock_resource "random_id" {
    defaults = {
      hex = "a1b2c3d4"
    }
  }
}

run "foundation_plan" {
  command = plan

  assert {
    condition     = aws_vpc.lab.cidr_block == "10.40.0.0/16"
    error_message = "The lab VPC CIDR changed."
  }

  assert {
    condition     = aws_subnet.lab.cidr_block == "10.40.10.0/24"
    error_message = "The single lab subnet CIDR changed."
  }

  assert {
    condition     = aws_instance.database_host.instance_type == "t3.medium"
    error_message = "The database host must remain t3.medium for version 1."
  }

  assert {
    condition     = aws_instance.database_host.associate_public_ip_address
    error_message = "EC2 needs outbound internet without a NAT Gateway."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.artifacts.block_public_policy
    error_message = "The artifact bucket must block public policies."
  }

  assert {
    condition     = aws_secretsmanager_secret.postgres.recovery_window_in_days == 0
    error_message = "The disposable lab secret must delete during teardown."
  }
}
