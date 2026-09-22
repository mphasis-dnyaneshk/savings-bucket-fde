module "network" {
  source       = "./modules/network"
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

module "registry" {
  source       = "./modules/registry"
  project_name = var.project_name
  environment  = var.environment
}

module "iam" {
  source       = "./modules/iam"
  project_name = var.project_name
  environment  = var.environment
}

module "database" {
  source            = "./modules/database"
  project_name      = var.project_name
  environment       = var.environment
  subnet_ids        = module.network.public_subnet_ids
  database_sg_id    = module.network.database_sg_id
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  database_name     = "savings_bucket"
  username          = var.db_username
  password          = var.db_password
}

module "messaging" {
  source       = "./modules/messaging"
  project_name = var.project_name
  environment  = var.environment
}

module "platform" {
  source              = "./modules/platform"
  project_name        = var.project_name
  environment         = var.environment
  vpc_id              = module.network.vpc_id
  public_subnet_ids   = module.network.public_subnet_ids
  alb_sg_id           = module.network.alb_sg_id
  service_sg_id       = module.network.service_sg_id
  execution_role_arn  = module.iam.execution_role_arn
  task_role_arn       = module.iam.task_role_arn
  ecr_repository_urls = module.registry.repository_urls
  database_url        = "postgresql://${var.db_username}:${var.db_password}@${module.database.address}:5432/savings_bucket"
  recurring_queue_arn = module.messaging.recurring_queue_arn
  recurring_queue_url = module.messaging.recurring_queue_url
  frontend_api_url    = "http://${module.platform.alb_dns_name}"
}
