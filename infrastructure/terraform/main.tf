locals {
  project_name = "aws-glue-postgres-mongodb-lab"
  common_tags = {
    Project     = "aws-glue-postgres-mongodb-lab"
    Environment = "lab"
    ManagedBy   = "terraform"
  }
}

data "aws_ssm_parameter" "amazon_linux_2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_vpc" "lab" {
  #checkov:skip=CKV2_AWS_11:Flow logs add a log group and IAM path that are unnecessary for a short manual lab.
  cidr_block           = "10.40.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.project_name}-vpc"
  }
}

# The default group is deliberately unusable; named groups below own all paths.
resource "aws_default_security_group" "lab" {
  vpc_id = aws_vpc.lab.id
}

resource "aws_subnet" "lab" {
  #checkov:skip=CKV_AWS_130:The public subnet supplies EC2 egress without a NAT Gateway; security groups expose no public ingress.
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = "10.40.10.0/24"
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.project_name}-subnet"
  }
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id

  tags = {
    Name = "${local.project_name}-igw"
  }
}

resource "aws_route_table" "lab" {
  vpc_id = aws_vpc.lab.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }

  tags = {
    Name = "${local.project_name}-routes"
  }
}

resource "aws_route_table_association" "lab" {
  subnet_id      = aws_subnet.lab.id
  route_table_id = aws_route_table.lab.id
}

resource "aws_security_group" "glue" {
  #checkov:skip=CKV_AWS_382:Glue needs service egress; inbound remains security-group-referenced only.
  #checkov:skip=CKV2_AWS_5:GLUE-030 attaches this pre-created group to Glue ENIs.
  name        = "glue"
  description = "Glue driver and executor communication plus lab egress"
  vpc_id      = aws_vpc.lab.id

  egress {
    description = "Lab service egress; no public ingress accompanies it"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.project_name}-glue-sg"
  }
}

# self-referencing All TCP is required for Glue driver/executor communication.
resource "aws_vpc_security_group_ingress_rule" "glue_self" {
  #checkov:skip=CKV_AWS_24:This rule references itself and has no CIDR-based SSH ingress.
  #checkov:skip=CKV_AWS_25:This rule references itself and has no CIDR-based RDP ingress.
  #checkov:skip=CKV_AWS_260:This rule references itself and has no CIDR-based HTTP ingress.
  security_group_id            = aws_security_group.glue.id
  referenced_security_group_id = aws_security_group.glue.id
  from_port                    = 0
  to_port                      = 65535
  ip_protocol                  = "tcp"
  description                  = "Glue driver and executor communication"
}

resource "aws_security_group" "database_host" {
  #checkov:skip=CKV_AWS_382:EC2 needs package, GitHub, Secrets Manager, and image-pull egress; there is no public inbound rule.
  name        = "database-host"
  description = "Database host with no public ingress"
  vpc_id      = aws_vpc.lab.id

  egress {
    description = "Package, repository, image, and AWS API egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.project_name}-database-host-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_glue" {
  security_group_id            = aws_security_group.database_host.id
  referenced_security_group_id = aws_security_group.glue.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from Glue only"
}

resource "aws_vpc_security_group_ingress_rule" "mongodb_from_glue" {
  security_group_id            = aws_security_group.database_host.id
  referenced_security_group_id = aws_security_group.glue.id
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
  description                  = "MongoDB from Glue only"
}

resource "aws_security_group" "endpoint" {
  #checkov:skip=CKV_AWS_382:The interface endpoint ENIs use return traffic; ingress is limited to the two lab groups.
  name        = "endpoint"
  description = "HTTPS access to interface endpoints"
  vpc_id      = aws_vpc.lab.id

  egress {
    description = "Interface endpoint response traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.project_name}-endpoint-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "endpoint_from_glue" {
  security_group_id            = aws_security_group.endpoint.id
  referenced_security_group_id = aws_security_group.glue.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Secrets Manager HTTPS from Glue"
}

resource "aws_vpc_security_group_ingress_rule" "endpoint_from_database_host" {
  security_group_id            = aws_security_group.endpoint.id
  referenced_security_group_id = aws_security_group.database_host.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Secrets Manager HTTPS from EC2"
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.lab.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.lab.id]

  tags = {
    Name = "${local.project_name}-s3-endpoint"
  }
}

resource "aws_vpc_endpoint" "secrets_manager" {
  vpc_id              = aws_vpc.lab.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.lab.id]
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.project_name}-secrets-endpoint"
  }
}

resource "aws_s3_bucket" "artifacts" {
  #checkov:skip=CKV_AWS_18:Access logging would require a second bucket for a short disposable personal lab.
  #checkov:skip=CKV_AWS_21:Versioning would retain disposable artifacts and complicate guaranteed teardown.
  #checkov:skip=CKV_AWS_144:Cross-Region replication conflicts with the single-Region disposable design.
  #checkov:skip=CKV_AWS_145:SSE-S3 meets the design requirement without an unnecessary lab-only KMS key.
  #checkov:skip=CKV2_AWS_62:Event notifications add no value to the manual on-demand workflow.
  bucket        = "${local.project_name}-${random_id.bucket_suffix.hex}"
  force_destroy = true

  tags = {
    Name = "${local.project_name}-artifacts"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  #checkov:skip=CKV_AWS_300:The rule already aborts incomplete multipart uploads after one day; this is a scanner parsing limitation.
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-temporary-objects"
    status = "Enabled"

    filter {
      prefix = "tmp/"
    }

    expiration {
      days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_secretsmanager_secret" "postgres" {
  #checkov:skip=CKV_AWS_149:The disposable lab uses the AWS-managed Secrets Manager key instead of a new CMK.
  #checkov:skip=CKV2_AWS_57:Values are generated per lab run and destroyed; a rotation service is production-only complexity.
  name                    = "/${local.project_name}/postgres"
  description             = "Disposable PostgreSQL lab credentials; value seeded outside Terraform"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret" "mongodb" {
  #checkov:skip=CKV_AWS_149:The disposable lab uses the AWS-managed Secrets Manager key instead of a new CMK.
  #checkov:skip=CKV2_AWS_57:Values are generated per lab run and destroyed; a rotation service is production-only complexity.
  name                    = "/${local.project_name}/mongodb"
  description             = "Disposable MongoDB lab credentials; value seeded outside Terraform"
  recovery_window_in_days = 0
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${local.project_name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ec2_secrets" {
  statement {
    sid       = "ReadLabDatabaseSecrets"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [aws_secretsmanager_secret.postgres.arn, aws_secretsmanager_secret.mongodb.arn]
  }
}

resource "aws_iam_role_policy" "ec2_secrets" {
  name   = "read-lab-database-secrets"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_secrets.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${local.project_name}-ec2"
  role = aws_iam_role.ec2.name
}

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${local.project_name}-glue"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

data "aws_iam_policy_document" "glue_network_read" {
  #checkov:skip=CKV_AWS_356:These EC2 Describe APIs do not support resource-level IAM constraints.
  statement {
    sid = "ReadGlueNetworkConfiguration"
    actions = [
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeRouteTables",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcAttribute",
      "ec2:DescribeVpcEndpoints",
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "glue_lab_access" {
  statement {
    sid     = "CreateGlueNetworkInterfaces"
    actions = ["ec2:CreateNetworkInterface"]
    resources = [
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:subnet/${aws_subnet.lab.id}",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:security-group/${aws_security_group.glue.id}",
    ]
  }

  statement {
    sid       = "DeleteGlueNetworkInterfaces"
    actions   = ["ec2:DeleteNetworkInterface"]
    resources = ["arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*"]
  }

  statement {
    sid       = "TagGlueNetworkInterfaces"
    actions   = ["ec2:CreateTags"]
    resources = ["arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*"]

    condition {
      test     = "ForAllValues:StringEquals"
      variable = "aws:TagKeys"
      values   = ["aws-glue-service-resource"]
    }
  }

  statement {
    sid = "WriteGlueLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws-glue/*",
      "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws-glue/*:*",
    ]
  }

  statement {
    sid       = "PublishGlueMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["AWS/Glue"]
    }
  }

  statement {
    sid = "UseLabArtifacts"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
  }

  statement {
    sid       = "ReadLabDatabaseSecrets"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [aws_secretsmanager_secret.postgres.arn, aws_secretsmanager_secret.mongodb.arn]
  }
}

resource "aws_iam_role_policy" "glue_lab_access" {
  name   = "lab-artifacts-and-secrets"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_lab_access.json
}

resource "aws_iam_role_policy" "glue_network_read" {
  name   = "lab-network-read"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_network_read.json
}

resource "aws_instance" "database_host" {
  #checkov:skip=CKV_AWS_88:A public IP supplies outbound package/image access without NAT; the group has no public ingress.
  #checkov:skip=CKV_AWS_126:Detailed monitoring adds cost without value for one short-lived manual lab instance.
  #checkov:skip=CKV_AWS_135:t3.medium is EBS-optimized by default; setting the argument adds no behavior.
  ami                         = data.aws_ssm_parameter.amazon_linux_2023_ami.value
  instance_type               = "t3.medium"
  subnet_id                   = aws_subnet.lab.id
  vpc_security_group_ids      = [aws_security_group.database_host.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repository_url = var.repository_url
    repository_ref = var.repository_ref
  })
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 30
  }

  depends_on = [aws_internet_gateway.lab]

  tags = {
    Name = "${local.project_name}-database-host"
  }
}
