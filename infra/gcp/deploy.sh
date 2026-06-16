#!/usr/bin/env bash
# Deploy Task Manager to Google Cloud Run.
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - Cloud Run API enabled (gcloud services enable run.googleapis.com)
#   - Cloud SQL PostgreSQL instance created
#   - Secrets in Secret Manager:
#       task-manager-database-url   (postgresql+asyncpg://...)
#       task-manager-secret-key
#   - GHCR images built and pushed (github.com publish workflow)
#
# Usage:
#   PROJECT_ID=my-project REGION=asia-southeast1 GITHUB_USERNAME=youruser ./infra/gcp/deploy.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:?Set REGION}"
GITHUB_USERNAME="${GITHUB_USERNAME:?Set GITHUB_USERNAME}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG (e.g. sha-\$GITHUB_SHA from the publish workflow)}"

# Substitute placeholders in service YAML files.
# YAML files use IMAGE_TAG as a literal token — replaced here with the versioned sha-<commit> tag.
substitute() {
  sed \
    -e "s/PROJECT_ID/$PROJECT_ID/g" \
    -e "s/REGION/$REGION/g" \
    -e "s/GITHUB_USERNAME/$GITHUB_USERNAME/g" \
    -e "s/IMAGE_TAG/$IMAGE_TAG/g" \
    "$1"
}

echo "→ Deploying API to Cloud Run..."
substitute infra/gcp/api-service.yaml | \
  gcloud run services replace - \
    --region "$REGION" --project "$PROJECT_ID"

echo "→ Making API publicly accessible..."
gcloud run services add-iam-policy-binding task-manager-api \
  --region "$REGION" --project "$PROJECT_ID" \
  --member="allUsers" --role="roles/run.invoker"

API_URL=$(gcloud run services describe task-manager-api \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "  API URL: $API_URL"

echo "→ Deploying frontend to Cloud Run..."
sed "s|https://task-manager-api-HASH-REGION.a.run.app|$API_URL|g" infra/gcp/frontend-service.yaml | \
  substitute /dev/stdin | \
  gcloud run services replace - \
    --region "$REGION" --project "$PROJECT_ID"

gcloud run services add-iam-policy-binding task-manager-frontend \
  --region "$REGION" --project "$PROJECT_ID" \
  --member="allUsers" --role="roles/run.invoker"

echo "✅ GCP Cloud Run deployment complete."
gcloud run services describe task-manager-frontend \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)"
