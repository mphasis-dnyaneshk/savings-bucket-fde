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
  eks_public_access_cidrs = var.eks_public_access_cidrs
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "eks_public_access_cidrs" {
  type        = list(string)
  description = "Your public IP CIDR allowed to access the EKS Kubernetes API endpoint."
}

output "frontend_url" { value = module.capstone.frontend_url }
output "alb_url" { value = module.capstone.alb_url }
