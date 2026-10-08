# AWS EKS Terraform Infrastructure

This directory provisions the capstone AWS environment for `dev` and `prod`. The application runs as Kubernetes Deployments on an Amazon EKS managed node group. A public Application Load Balancer routes browser and API traffic to Kubernetes NodePort Services.

## Included resources

- VPC with two public subnets, Internet Gateway, routing, and security groups.
- ECR repositories for the frontend and five FastAPI services.
- EKS control plane, managed node group, and CloudWatch control-plane logs.
- Application Load Balancer with frontend default routing and backend path routing.
- NodePort target groups attached to the EKS managed node group.
- Small RDS PostgreSQL instance using the shared subnet group.
- SQS recurring-contribution queue and dead-letter queue.
- EventBridge event bus and recurring schedule rule.
- EKS cluster and node IAM roles.

This is a simplified capstone deployment. Worker nodes and RDS use public subnets; restrict the public EKS API endpoint to trusted IP ranges before sharing the environment. Private subnets, NAT Gateway, API Gateway, Cognito, WAF, Shield, VPC endpoints, multi-region recovery, workload-specific IAM roles, and production-grade secrets management remain follow-up work.

## Layout

```text
infra/
├── kubernetes/application.yaml
└── terraform/
    ├── modules/
    │   ├── network/
    │   ├── registry/
    │   ├── iam/
    │   ├── database/
    │   ├── messaging/
    │   └── platform/
    └── environments/
        ├── dev/main.tf
        └── prod/main.tf
```

Both environments use the same cluster and node sizes. Each environment has its own Terraform state and AWS resources.

## Prerequisites

- Terraform >= 1.6.
- AWS CLI authenticated to the target account.
- `kubectl`, Docker, `jq`, `envsubst` (GNU gettext), Git Bash, and Python.
- An AWS region with at least two available Availability Zones.
- A database password supplied through `TF_VAR_db_password`.

Do not commit passwords, Terraform state, or plan files. The EKS public API endpoint requires an explicit source CIDR allowlist; set it to your public IP with a `/32` mask.

## Provision infrastructure

From Git Bash at the repository root:

```bash
export AWS_REGION=us-east-1
export TF_VAR_db_password='use-a-capstone-only-password'
export TF_VAR_eks_public_access_cidrs='["YOUR_PUBLIC_IP/32"]'

terraform -chdir=infra/terraform/environments/dev init
terraform -chdir=infra/terraform/environments/dev plan -var="aws_region=${AWS_REGION}"
terraform -chdir=infra/terraform/environments/dev apply -var="aws_region=${AWS_REGION}"
```

The local backend writes `terraform-dev.tfstate` under the environment directory. Use a remote backend before collaborative use. The `prod` environment has the same capstone sizing and is not a production banking environment.

## Deploy application workloads

Build and push all six images, update the local Kubernetes context, create the database Secret, run the migration Job inside EKS, and apply the Kubernetes Deployments and NodePort Services:

```bash
export ENVIRONMENT=dev
export AWS_REGION=us-east-1
export TF_VAR_db_password='use-a-capstone-only-password'
bash ./scripts/deploy-eks.sh
```

The deployment script requires AWS credentials with ECR/EKS access and Docker. It uses Terraform outputs, builds the frontend with the ALB URL embedded in its Vite configuration, pushes tagged images, applies the database migration, then waits for all six Deployments to become ready. Set `IMAGE_TAG` to override the default Git commit tag.

The ALB sends frontend traffic to NodePort `30080`; backend NodePorts `30081` through `30085` receive path-routed API traffic. The security group permits those ports only from the ALB. Kubernetes workload logs can be inspected with `kubectl logs -n savings-bucket deployment/<service-name>`; EKS control-plane logs are retained in CloudWatch for seven days.

## Outputs

Terraform exports `alb_url`, `eks_cluster_name`, `eks_node_group_name`, `database_address`, `database_username`, `ecr_repository_urls`, and `recurring_queue_url`.

Open the application at the `alb_url` output. The frontend uses the `customer-001` local mock identity. Real OIDC/JWT validation and banking integration are not enabled.

## Destroy an environment

Destroy only after the demonstration is complete:

```bash
terraform -chdir=infra/terraform/environments/dev destroy -var="aws_region=${AWS_REGION}"
```

RDS deletion protection is disabled and final snapshots are skipped for this capstone. EKS incurs a control-plane charge and the managed node group incurs EC2 charges while running; destroy unused environments.
