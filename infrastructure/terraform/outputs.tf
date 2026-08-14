output "aws_region" {
  description = "Region containing the lab."
  value       = var.aws_region
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
  description = "MongoDB secret container name; the value is seeded separately."
  value       = aws_secretsmanager_secret.mongodb.name
}

output "database_instance_id" {
  description = "SSM-managed database host instance ID."
  value       = aws_instance.database_host.id
}

output "database_private_ip" {
  description = "Private database host address used in the two secret values."
  value       = aws_instance.database_host.private_ip
}

output "glue_role_arn" {
  description = "IAM role used by later Glue tasks."
  value       = aws_iam_role.glue.arn
}
