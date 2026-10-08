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
  source                   = "./modules/platform"
  project_name             = var.project_name
  environment              = var.environment
  vpc_id                   = module.network.vpc_id
  public_subnet_ids        = module.network.public_subnet_ids
  alb_sg_id                = module.network.alb_sg_id
  cluster_role_arn         = module.iam.cluster_role_arn
  node_role_arn            = module.iam.node_role_arn
  ecr_repository_urls      = module.registry.repository_urls
  eks_public_access_cidrs = var.eks_public_access_cidrs

  depends_on = [module.iam]
}

resource "aws_security_group_rule" "eks_nodes_from_alb" {
  type                     = "ingress"
  from_port                = 30080
  to_port                  = 30085
  protocol                 = "tcp"
  security_group_id        = module.platform.cluster_security_group_id
  source_security_group_id = module.network.alb_sg_id
  description              = "Allow ALB traffic to the application NodePort services."
}

resource "aws_security_group_rule" "database_from_eks" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.network.database_sg_id
  source_security_group_id = module.platform.cluster_security_group_id
  description              = "Allow EKS workloads to connect to PostgreSQL."
}
