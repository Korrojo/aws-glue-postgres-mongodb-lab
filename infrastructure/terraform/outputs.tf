output "aws_region" {
  description = "Region containing the lab."
  value       = var.aws_region
}

output "aws_account_id" {
  description = "Account bound to this local Terraform state; used by mutation safety checks."
  value       = data.aws_caller_identity.current.account_id
}

output "vpc_id" {
  description = "Dedicated lab VPC ID."
  value       = aws_vpc.lab.id
}

output "subnet_id" {
  description = "Single lab subnet used by EC2 and Glue."
  value       = aws_subnet.lab.id
}

output "database_host_security_group_id" {
  description = "Security group attached to the database EC2 host."
  value       = aws_security_group.database_host.id
}

output "glue_security_group_id" {
  description = "Security group reserved for Glue ENIs."
  value       = aws_security_group.glue.id
}

output "artifact_bucket_name" {
  description = "Encrypted private S3 bucket for Glue artifacts."
  value       = aws_s3_bucket.artifacts.id
}

output "postgres_secret_name" {
  description = "PostgreSQL secret container name; the value is seeded separately."
  value       = aws_secretsmanager_secret.postgres.name
}

output "mongodb_secret_name" {
  description = "MongoDB bootstrap administrator secret container name; the value is seeded separately."
  value       = aws_secretsmanager_secret.mongodb.name
}

output "mongodb_glue_secret_name" {
  description = "MongoDB connector-only secret container name; the value is seeded separately."
  value       = aws_secretsmanager_secret.mongodb_glue.name
}

output "database_instance_id" {
  description = "SSM-managed database host instance ID."
  value       = aws_instance.database_host.id
}

output "database_private_ip" {
  description = "Private database host address used in the three secret values."
  value       = aws_instance.database_host.private_ip
}

output "glue_role_arn" {
  description = "IAM role used by the Glue crawler and job."
  value       = aws_iam_role.glue.arn
}

output "glue_catalog_database_name" {
  description = "Catalog database containing exactly the two sales source tables."
  value       = aws_glue_catalog_database.lab.name
}

output "postgres_glue_connection_name" {
  description = "Named PostgreSQL JDBC connection."
  value       = aws_glue_connection.postgres.name
}

output "mongodb_glue_connection_name" {
  description = "Named native MongoDB connection."
  value       = aws_glue_connection.mongodb.name
}

output "glue_crawler_name" {
  description = "Unscheduled crawler started only by the user."
  value       = aws_glue_crawler.orders.name
}

output "glue_job_name" {
  description = "Unscheduled Glue 5.1 snapshot job started only by the user."
  value       = aws_glue_job.orders_to_mongodb.name
}

output "glue_artifact_prefix" {
  description = "Deterministic S3 prefix used by the artifact deployment script."
  value       = "s3://${aws_s3_bucket.artifacts.id}/glue/artifacts/"
}
