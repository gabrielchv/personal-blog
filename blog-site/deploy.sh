#!/bin/bash

# Configuration
PROJECT_ID="blog-473919"
REGION="us-central1"
SERVICE_NAME="personal-blog"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Personal Blog to Cloud Run..."
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo "📦 Setting GCP project to: ${PROJECT_ID}"
gcloud config set project ${PROJECT_ID}

# Get current user email
USER_EMAIL=$(gcloud config get-value account)
echo "👤 Authenticated as: ${USER_EMAIL}"

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com

# Grant Cloud Build permissions
echo "🔐 Granting Cloud Build permissions..."
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/storage.admin" \
    --quiet 2>/dev/null || true

# Load .env if exists
if [ -f ../.env ]; then
    echo "📝 Loading environment variables from .env..."
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Build the Docker image
echo "🏗️  Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Build failed! Trying to grant additional permissions..."
    echo "Run this command manually:"
    echo ""
    echo "gcloud projects add-iam-policy-binding ${PROJECT_ID} \\"
    echo "  --member='user:${USER_EMAIL}' \\"
    echo "  --role='roles/cloudbuild.builds.editor'"
    echo ""
    exit 1
fi

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-blog-posts-gazerah}" \
  --set-env-vars "ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}" \
  --set-env-vars "SECRET_KEY=${SECRET_KEY:-change-this-secret-key}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)' 2>/dev/null)

echo ""
echo "✅ Deployment complete!"
echo "🌐 Your blog is live at: ${SERVICE_URL}"
echo "🔑 Admin panel: ${SERVICE_URL}/admin"
echo ""
echo "📝 Your Cloud Run service will use default GCS credentials"
echo "   No credentials.json needed in production!"
