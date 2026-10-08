#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD)}"
TF_DIR="$ROOT_DIR/infra/terraform/environments/$ENVIRONMENT"

if [[ ! -d "$TF_DIR" ]]; then
  echo "Unknown environment: $ENVIRONMENT" >&2
  exit 1
fi

for command in aws docker envsubst jq kubectl python terraform; do
  command -v "$command" >/dev/null || {
    echo "Required command not found: $command" >&2
    exit 1
  }
done

: "${TF_VAR_db_password:?Set TF_VAR_db_password to the RDS password used by Terraform}"

CLUSTER_NAME="$(terraform -chdir="$TF_DIR" output -raw eks_cluster_name)"
ALB_URL="$(terraform -chdir="$TF_DIR" output -raw alb_url)"
DB_HOST="$(terraform -chdir="$TF_DIR" output -raw database_address)"
DB_USERNAME="$(terraform -chdir="$TF_DIR" output -raw database_username)"
DATABASE_URL="$(DB_HOST="$DB_HOST" DB_USERNAME="$DB_USERNAME" python -c 'import os; from urllib.parse import quote; print("postgresql://{}:{}@{}:5432/savings_bucket".format(os.environ["DB_USERNAME"], quote(os.environ["TF_VAR_db_password"], safe=""), os.environ["DB_HOST"]))')"

export AWS_REGION ENVIRONMENT IMAGE_TAG
export DATABASE_URL

aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
ECR_REPOSITORIES="$(terraform -chdir="$TF_DIR" output -json ecr_repository_urls)"
ECR_REGISTRY="$(jq -r '.frontend | split("/")[0]' <<< "$ECR_REPOSITORIES")"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

for service in frontend bucket-service contribution-service withdrawal-service recurring-contribution-service notification-service; do
  repository="$(jq -r --arg service "$service" '.[$service]' <<< "$ECR_REPOSITORIES")"
  image="$repository:$IMAGE_TAG"

  if [[ "$service" == "frontend" ]]; then
    docker build -f "$ROOT_DIR/frontend/Dockerfile" \
      --build-arg VITE_CUSTOMER_ID=customer-001 \
      --build-arg VITE_BUCKET_API_URL="$ALB_URL" \
      --build-arg VITE_CONTRIBUTION_API_URL="$ALB_URL" \
      --build-arg VITE_WITHDRAWAL_API_URL="$ALB_URL" \
      --build-arg VITE_RECURRING_API_URL="$ALB_URL" \
      --build-arg VITE_NOTIFICATION_API_URL="$ALB_URL" \
      -t "$image" "$ROOT_DIR/frontend"
  else
    module="${service//-/_}"
    docker build -f "$ROOT_DIR/Dockerfile" \
      --build-arg "SERVICE_MODULE=services.${module}.main" \
      -t "$image" "$ROOT_DIR"
  fi

  docker push "$image"
  variable_name="ECR_$(printf '%s' "${service//-/_}" | tr '[:lower:]' '[:upper:]')"
  printf -v "$variable_name" '%s' "$repository"
  export "$variable_name"
done

kubectl create namespace savings-bucket --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic savings-bucket-database \
  --namespace savings-bucket \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap savings-bucket-migration \
  --namespace savings-bucket \
  --from-file=001_foundation.sql="$ROOT_DIR/db/migrations/001_foundation.sql" \
  --from-file=002_bucket_archive.sql="$ROOT_DIR/db/migrations/002_bucket_archive.sql" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl delete job savings-bucket-migration --namespace savings-bucket --ignore-not-found
kubectl apply -f "$ROOT_DIR/infra/kubernetes/migration.yaml"
kubectl wait --for=condition=complete job/savings-bucket-migration \
  --namespace savings-bucket --timeout=5m

envsubst < "$ROOT_DIR/infra/kubernetes/application.yaml" | kubectl apply -f -
kubectl rollout status deployment/frontend --namespace savings-bucket --timeout=5m
kubectl rollout status deployment/bucket-service --namespace savings-bucket --timeout=5m
kubectl rollout status deployment/contribution-service --namespace savings-bucket --timeout=5m
kubectl rollout status deployment/withdrawal-service --namespace savings-bucket --timeout=5m
kubectl rollout status deployment/recurring-contribution-service --namespace savings-bucket --timeout=5m
kubectl rollout status deployment/notification-service --namespace savings-bucket --timeout=5m
printf 'Application deployed to %s\n' "$ALB_URL"