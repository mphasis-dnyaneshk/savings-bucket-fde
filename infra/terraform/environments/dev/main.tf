terraform {
  backend "local" {
    path = "terraform-dev.tfstate"
  }
}

module "capstone" {
  source = "../.."

  aws_region  = var.aws_region
  environment = "dev"
  db_password = var.db_password
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "db_password" {
  type      = string
  sensitive = true
}

output "frontend_url" { value = module.capstone.frontend_url }
output "alb_url" { value = module.capstone.alb_url }
