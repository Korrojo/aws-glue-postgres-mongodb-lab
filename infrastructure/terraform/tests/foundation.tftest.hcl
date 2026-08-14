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

  mock_resource "aws_iam_role" {
    defaults = {
      arn  = "arn:aws:iam::123456789012:role/mock-lab-role"
      id   = "mock-lab-role"
      name = "mock-lab-role"
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
      aws_secretsmanager_secret.mongodb.recovery_window_in_days == 0,
      aws_secretsmanager_secret.mongodb_glue.recovery_window_in_days == 0,
    ])
    error_message = "Both disposable MongoDB secrets must delete during teardown."
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

  assert {
    condition = (
      aws_glue_connection.postgres.physical_connection_requirements[0].subnet_id ==
      aws_glue_connection.mongodb.physical_connection_requirements[0].subnet_id
    )
    error_message = "Both Glue connections must use the one lab subnet."
  }

  assert {
    condition = (
      aws_glue_connection.postgres.connection_properties["SECRET_ID"] == aws_secretsmanager_secret.postgres.name &&
      aws_glue_connection.mongodb.connection_properties["SECRET_ID"] == aws_secretsmanager_secret.mongodb_glue.name &&
      toset(keys(aws_glue_connection.postgres.connection_properties)) == toset(["JDBC_CONNECTION_URL", "SECRET_ID"]) &&
      toset(keys(aws_glue_connection.mongodb.connection_properties)) == toset(["CONNECTION_URL", "SECRET_ID"])
    )
    error_message = "Glue connections must use only credential-free URLs and named Secrets Manager references."
  }

  assert {
    condition = (
      toset(aws_glue_connection.postgres.physical_connection_requirements[0].security_group_id_list) == toset([aws_security_group.glue.id]) &&
      toset(aws_glue_connection.mongodb.physical_connection_requirements[0].security_group_id_list) == toset([aws_security_group.glue.id])
    )
    error_message = "Both Glue connections must use only the one Glue security group."
  }

  assert {
    condition     = aws_glue_crawler.orders.schedule == null
    error_message = "The crawler must remain unscheduled and user-run only."
  }

  assert {
    condition = toset([
      for target in aws_glue_crawler.orders.jdbc_target : target.path
    ]) == toset(["sales_lab/sales/orders", "sales_lab/sales/order_items"])
    error_message = "The crawler must target exactly the two sales tables."
  }

  assert {
    condition = (
      aws_glue_job.orders_to_mongodb.glue_version == "5.1" &&
      aws_glue_job.orders_to_mongodb.worker_type == "G.1X" &&
      aws_glue_job.orders_to_mongodb.number_of_workers == 2 &&
      aws_glue_job.orders_to_mongodb.execution_property[0].max_concurrent_runs == 1 &&
      toset(aws_glue_job.orders_to_mongodb.connections) == toset([
        aws_glue_connection.postgres.name,
        aws_glue_connection.mongodb.name,
      ])
    )
    error_message = "The job must remain on the small Glue 5.1 lab baseline."
  }

  assert {
    condition = (
      aws_glue_job.orders_to_mongodb.default_arguments["--TempDir"] ==
      "s3://${aws_s3_bucket.artifacts.id}/tmp/"
    )
    error_message = "The job must use only the Terraform-managed temporary S3 prefix."
  }
}
