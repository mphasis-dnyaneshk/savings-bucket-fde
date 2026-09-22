# AWS Terraform Infrastructure

This directory provisions the capstone AWS environment with the same resource sizes and module composition for `dev` and `prod`.

## Included resources

- VPC with two public subnets, Internet Gateway, public routing, and basic security groups.
- ECR repositories for the frontend and five FastAPI services.
- ECS Fargate cluster and services for the frontend plus backend services.
- Application Load Balancer with frontend default routing and backend path routing.
- Small RDS PostgreSQL instance using the shared public subnet group.
- SQS recurring-contribution queue and dead-letter queue.
- EventBridge event bus and recurring schedule rule.
- CloudWatch log groups for each ECS service.
- ECS execution and task IAM roles.

This is intentionally a simplified capstone deployment. Private subnets, NAT Gateway, API Gateway, Cognito, WAF, Shield, VPC endpoints, multi-region recovery, and advanced security controls are deferred.

## Layout

```text
infra/terraform/
├── modules/
│   ├── network/
│   ├── registry/
│   ├── iam/
│   ├── database/
│   ├── messaging/
│   └── platform/
├── environments/
│   ├── dev/main.tf
│   └── prod/main.tf
├── main.tf
├── outputs.tf
└── versions.tf
```

Both environments call the same root module with the same CPU, memory, database class, storage, and desired counts. They differ only by environment name and Terraform state path.

## Prerequisites

- Terraform >= 1.6.
- AWS CLI authenticated to the target account.
- An AWS region with at least two available Availability Zones.
- A database password supplied through `TF_VAR_db_password`.

Do not commit passwords, Terraform state, or plan files.

## Deploy dev

From Git Bash at the repository root:

```bash
export AWS_REGION=us-east-1
export TF_VAR_db_password='use-a-capstone-only-password'

terraform -chdir=infra/terraform/environments/dev init
terraform -chdir=infra/terraform/environments/dev plan -var="aws_region=${AWS_REGION}"
terraform -chdir=infra/terraform/environments/dev apply -var="aws_region=${AWS_REGION}"
```

The local backend writes `terraform-dev.tfstate` under the environment directory. Use a remote backend before collaborative or production use.

## Deploy prod

The `prod` environment intentionally uses identical resource sizes for this capstone:

```bash
export AWS_REGION=us-east-1
export TF_VAR_db_password='use-a-capstone-only-password'

terraform -chdir=infra/terraform/environments/prod init
terraform -chdir=infra/terraform/environments/prod plan -var="aws_region=${AWS_REGION}"
terraform -chdir=infra/terraform/environments/prod apply -var="aws_region=${AWS_REGION}"
```

For this capstone, `prod` is a second isolated environment, not a production banking environment. Use mock banking mode and synthetic customer data.

## Build and push images

Terraform creates ECR repositories and ECS services, but it does not build application images. Build and push application images before ECS tasks can become healthy.

The frontend image must be built with the deployed ALB URL in its Vite environment variables because Vite embeds `VITE_*` values at build time. The backend images use the existing root `Dockerfile` and service module build argument.

After `terraform apply`, get the ALB URL:

```bash
terraform -chdir=infra/terraform/environments/dev output -raw alb_url
```

Build and push the frontend and each backend image to its corresponding ECR repository with the expected `latest` tag.

## Destroy an environment

Destroy only after the demonstration is complete:

```bash
terraform -chdir=infra/terraform/environments/dev destroy -var="aws_region=${AWS_REGION}"
```

RDS deletion protection is disabled and final snapshots are skipped for this capstone to keep teardown straightforward. Do not use these settings for real financial workloads.
