variable "project_name" { type = string }
variable "environment" { type = string }

locals {
  repositories = [
    "frontend",
    "bucket-service",
    "contribution-service",
    "withdrawal-service",
    "recurring-contribution-service",
    "notification-service",
  ]
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(local.repositories)
  name                 = "${var.project_name}-${var.environment}-${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }
}

output "repository_urls" {
  value = { for name, repository in aws_ecr_repository.this : name => repository.repository_url }
}
