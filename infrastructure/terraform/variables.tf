variable "aws_region" {
  description = "Single AWS Region used by the lab."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "Version 1 of this lab is fixed to us-east-1."
  }
}

variable "availability_zone" {
  description = "One Availability Zone for the lab subnet."
  type        = string
  default     = "us-east-1a"

  validation {
    condition     = startswith(var.availability_zone, "us-east-1")
    error_message = "The Availability Zone must belong to us-east-1."
  }
}

variable "repository_url" {
  description = "Public canonical repository cloned by EC2."
  type        = string
  default     = "https://github.com/Korrojo/aws-glue-postgres-mongodb-lab.git"

  validation {
    condition     = var.repository_url == "https://github.com/Korrojo/aws-glue-postgres-mongodb-lab.git"
    error_message = "The core EC2 workflow clones only the canonical public repository."
  }
}

variable "repository_ref" {
  description = "Reviewed branch cloned by EC2."
  type        = string
  default     = "main"

  validation {
    condition     = can(regex("^[A-Za-z0-9._/-]+$", var.repository_ref)) && !startswith(var.repository_ref, "-")
    error_message = "The repository ref must be a non-option Git branch or tag name."
  }
}
