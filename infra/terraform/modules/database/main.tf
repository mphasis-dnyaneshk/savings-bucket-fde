variable "project_name" { type = string }
variable "environment" { type = string }
variable "subnet_ids" { type = list(string) }
variable "database_sg_id" { type = string }
variable "instance_class" { type = string }
variable "allocated_storage" { type = number }
variable "database_name" { type = string }
variable "username" { type = string }
variable "password" {
  type      = string
  sensitive = true
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-${var.environment}"
  subnet_ids = var.subnet_ids
}

resource "aws_db_instance" "this" {
  identifier             = "${var.project_name}-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.instance_class
  allocated_storage      = var.allocated_storage
  storage_type           = "gp3"
  db_name                = var.database_name
  username               = var.username
  password               = var.password
  port                   = 5432
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.database_sg_id]
  publicly_accessible    = true
  skip_final_snapshot    = true
  deletion_protection    = false
  backup_retention_period = 1
}

output "address" { value = aws_db_instance.this.address }
output "port" { value = aws_db_instance.this.port }
