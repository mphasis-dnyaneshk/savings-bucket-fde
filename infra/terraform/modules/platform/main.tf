variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "alb_sg_id" { type = string }
variable "cluster_role_arn" { type = string }
variable "node_role_arn" { type = string }
variable "eks_public_access_cidrs" { type = list(string) }
variable "ecr_repository_urls" { type = map(string) }

locals {
  cluster_name = "${var.project_name}-${var.environment}"
  backend_services = {
    bucket-service = {
      node_port = 30081
      priority  = 20
      paths     = ["/v1/buckets*", "/internal/buckets/*"]
    }
    contribution-service = {
      node_port = 30082
      priority  = 10
      paths     = ["/v1/buckets/*/contributions*"]
    }
    withdrawal-service = {
      node_port = 30083
      priority  = 11
      paths     = ["/v1/buckets/*/withdrawals*"]
    }
    recurring-contribution-service = {
      node_port = 30084
      priority  = 12
      paths     = ["/v1/buckets/*/recurring-contributions*"]
    }
    notification-service = {
      node_port = 30085
      priority  = 13
      paths     = ["/v1/notifications*", "/internal/notifications*"]
    }
  }
}

resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = 7
}

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  role_arn = var.cluster_role_arn

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids              = var.public_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.eks_public_access_cidrs
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  depends_on = [aws_cloudwatch_log_group.eks_cluster]
}

resource "aws_eks_node_group" "workers" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-workers"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.public_subnet_ids
  instance_types  = ["t3.medium"]
  disk_size       = 20

  scaling_config {
    desired_size = 2
    min_size     = 2
    max_size     = 3
  }

  update_config {
    max_unavailable = 1
  }
}

resource "aws_lb" "this" {
  name               = local.cluster_name
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_sg_id]
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.project_name}-${var.environment}-web"
  port        = 30080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    path                = "/"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }
}

resource "aws_lb_target_group" "backend" {
  for_each    = local.backend_services
  name        = substr("${var.project_name}-${var.environment}-${each.key}", 0, 32)
  port        = each.value.node_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    path                = "/health/live"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }
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

resource "aws_lb_listener_rule" "backend" {
  for_each     = local.backend_services
  listener_arn = aws_lb_listener.http.arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value.paths
    }
  }
}

resource "aws_autoscaling_attachment" "frontend" {
  autoscaling_group_name = aws_eks_node_group.workers.resources[0].autoscaling_groups[0].name
  lb_target_group_arn    = aws_lb_target_group.frontend.arn
}

resource "aws_autoscaling_attachment" "backend" {
  for_each               = local.backend_services
  autoscaling_group_name = aws_eks_node_group.workers.resources[0].autoscaling_groups[0].name
  lb_target_group_arn    = aws_lb_target_group.backend[each.key].arn
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "node_group_name" {
  value = aws_eks_node_group.workers.node_group_name
}

output "cluster_security_group_id" {
  value = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}
