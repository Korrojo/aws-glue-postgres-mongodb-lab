mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
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
  command = apply

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

  assert {
    condition = alltrue([
      length(aws_security_group.glue.ingress) == 0,
      length(aws_security_group.database_host.ingress) == 0,
      length(aws_security_group.endpoint.ingress) == 0,
      aws_vpc_security_group_ingress_rule.glue_self.cidr_ipv4 == null,
      aws_vpc_security_group_ingress_rule.glue_self.cidr_ipv6 == null,
      aws_vpc_security_group_ingress_rule.postgres_from_glue.cidr_ipv4 == null,
      aws_vpc_security_group_ingress_rule.postgres_from_glue.cidr_ipv6 == null,
      aws_vpc_security_group_ingress_rule.mongodb_from_glue.cidr_ipv4 == null,
      aws_vpc_security_group_ingress_rule.mongodb_from_glue.cidr_ipv6 == null,
      aws_vpc_security_group_ingress_rule.endpoint_from_glue.cidr_ipv4 == null,
      aws_vpc_security_group_ingress_rule.endpoint_from_glue.cidr_ipv6 == null,
      aws_vpc_security_group_ingress_rule.endpoint_from_database_host.cidr_ipv4 == null,
      aws_vpc_security_group_ingress_rule.endpoint_from_database_host.cidr_ipv6 == null,
    ])
    error_message = "Every ingress path must reference another lab security group; public CIDRs and inline ingress are forbidden."
  }
}
