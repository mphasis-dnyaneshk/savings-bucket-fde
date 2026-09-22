terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "savings-bucket"
      Environment = var.environment
      ManagedBy   = "terraform"
      Capstone    = "true"
    }
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region for the capstone environment."
}

variable "environment" {
  type        = string
  description = "Environment name, such as dev or prod."
}

variable "project_name" {
  type    = string
  default = "savings-bucket"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "db_username" {
  type    = string
  default = "savings"
}

variable "db_password" {
  type      = string
  sensitive = true
}
