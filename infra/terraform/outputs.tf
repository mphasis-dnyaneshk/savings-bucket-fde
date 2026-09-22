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
