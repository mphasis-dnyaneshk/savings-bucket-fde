output "alb_url" {
  value = "http://${module.platform.alb_dns_name}"
}

output "frontend_url" {
  value = "http://${module.platform.alb_dns_name}"
}

output "database_address" {
  value = module.database.address
}

output "ecr_repository_urls" {
  value = module.registry.repository_urls
}

output "recurring_queue_url" {
  value = module.messaging.recurring_queue_url
}

output "eks_cluster_name" {
  value = module.platform.cluster_name
}

output "eks_node_group_name" {
  value = module.platform.node_group_name
}

output "database_username" {
  value = var.db_username
}
