#!/usr/bin/env bash
# Deploy Task Manager to AWS ECS Fargate.
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - jq installed
#   - ECS cluster, VPC, subnets, security groups, ALB created (see aws/README.md)
#   - Secrets in AWS Secrets Manager:
#       task-manager/database-url  (postgresql+asyncpg://...)
#       task-manager/secret-key
#   - GHCR images built and pushed (github.com publish workflow)
#
# Usage:
#   REGION=ap-southeast-1 ACCOUNT_ID=123456789 GITHUB_USERNAME=youruser ./aws/deploy.sh

set -euo pipefail

REGION="${REGION:?Set REGION}"
ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
GITHUB_USERNAME="${GITHUB_USERNAME:?Set GITHUB_USERNAME}"
CLUSTER="${CLUSTER:-task-manager}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG (e.g. sha-\$GITHUB_SHA from the publish workflow)}"

# Substitute placeholders in task definitions.
# JSON files use IMAGE_TAG as a literal token — replaced here with the versioned sha-<commit> tag.
substitute() {
  sed \
    -e "s/ACCOUNT_ID/$ACCOUNT_ID/g" \
    -e "s/REGION/$REGION/g" \
    -e "s/GITHUB_USERNAME/$GITHUB_USERNAME/g" \
    -e "s/IMAGE_TAG/$IMAGE_TAG/g" \
    "$1"
}

echo "→ Registering ECS task definitions..."
API_ARN=$(substitute aws/ecs/api-task.json | \
  aws ecs register-task-definition --region "$REGION" \
    --cli-input-json file:///dev/stdin \
    --query "taskDefinition.taskDefinitionArn" --output text)

FRONTEND_ARN=$(substitute aws/ecs/frontend-task.json | \
  aws ecs register-task-definition --region "$REGION" \
    --cli-input-json file:///dev/stdin \
    --query "taskDefinition.taskDefinitionArn" --output text)

echo "→ Updating ECS services..."
aws ecs update-service --region "$REGION" --cluster "$CLUSTER" \
  --service task-manager-api      --task-definition "$API_ARN"      --force-new-deployment
aws ecs update-service --region "$REGION" --cluster "$CLUSTER" \
  --service task-manager-frontend --task-definition "$FRONTEND_ARN" --force-new-deployment

echo "→ Waiting for stable deployment..."
aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" \
  --services task-manager-api task-manager-frontend

echo "✅ AWS ECS deployment complete."
