variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "alb_sg_id" { type = string }
variable "service_sg_id" { type = string }
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
variable "ecr_repository_urls" { type = map(string) }
variable "database_url" {
  type      = string
  sensitive = true
}
variable "recurring_queue_arn" { type = string }
variable "recurring_queue_url" { type = string }
variable "frontend_api_url" { type = string }

locals {
  backend_services = {
    bucket-service                 = { module = "services.bucket_service.main", port = 8000, path = "/v1/buckets*" }
    contribution-service           = { module = "services.contribution_service.main", port = 8000, path = "/v1/buckets/*/contributions*" }
    withdrawal-service             = { module = "services.withdrawal_service.main", port = 8000, path = "/v1/buckets/*/withdrawals*" }
    recurring-contribution-service = { module = "services.recurring_contribution_service.main", port = 8000, path = "/v1/buckets/*/recurring-contributions*" }
    notification-service           = { module = "services.notification_service.main", port = 8000, path = "/v1/notifications*" }
  }
}

resource "aws_cloudwatch_log_group" "service" {
  for_each          = merge(local.backend_services, { frontend = { module = "", port = 80, path = "/*" } })
  name              = "/ecs/${var.project_name}/${var.environment}/${each.key}"
  retention_in_days = 7
}

resource "aws_ecs_cluster" "this" {
  name = "${var.project_name}-${var.environment}"
}

resource "aws_lb" "this" {
  name               = "${var.project_name}-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_sg_id]
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.project_name}-${var.environment}-web"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check { path = "/" }
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-${var.environment}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${var.ecr_repository_urls["frontend"]}:latest"
    essential = true
    portMappings = [{ containerPort = 80, hostPort = 80, protocol = "tcp" }]
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.service["frontend"].name, "awslogs-region" = data.aws_region.current.name, "awslogs-stream-prefix" = "ecs" } }
  }])
}

resource "aws_ecs_service" "frontend" {
  name            = "frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.service_sg_id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }
  depends_on = [aws_lb_listener.http]
}

resource "aws_lb_target_group" "backend" {
  for_each    = local.backend_services
  name        = substr("${var.project_name}-${var.environment}-${each.key}", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check { path = "/health/live" }
}

resource "aws_lb_listener_rule" "backend" {
  for_each     = local.backend_services
  listener_arn = aws_lb_listener.http.arn
  priority     = index(keys(local.backend_services), each.key) + 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[each.key].arn
  }
  condition {
    path_pattern {
      values = [each.value.path]
    }
  }
}

resource "aws_ecs_task_definition" "backend" {
  for_each                 = local.backend_services
  family                   = "${var.project_name}-${var.environment}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions = jsonencode([{
    name      = each.key
    image     = "${var.ecr_repository_urls[each.key]}:latest"
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "SERVICE_NAME", value = each.key },
      { name = "APP_ENV", value = "aws-capstone" },
      { name = "DATABASE_URL", value = var.database_url },
      { name = "BANKING_ADAPTER_MODE", value = "mock" },
      { name = "EVENT_BUS_MODE", value = "aws" },
      { name = "SQS_MODE", value = "aws" },
      { name = "RECURRING_QUEUE_URL", value = var.recurring_queue_url },
    ]
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.service[each.key].name, "awslogs-region" = data.aws_region.current.name, "awslogs-stream-prefix" = "ecs" } }
  }])
}

resource "aws_ecs_service" "backend" {
  for_each        = local.backend_services
  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.service_sg_id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.backend[each.key].arn
    container_name   = each.key
    container_port   = 8000
  }
}

data "aws_region" "current" {}

output "alb_dns_name" { value = aws_lb.this.dns_name }
output "frontend_service_name" { value = aws_ecs_service.frontend.name }
output "execution_role_arn" { value = var.execution_role_arn }
output "task_role_arn" { value = var.task_role_arn }
