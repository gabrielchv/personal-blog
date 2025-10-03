#!/bin/bash

# This script helps you set up secrets in Cloud Run

PROJECT_ID="your-gcp-project-id"  # CHANGE THIS!
SERVICE_NAME="personal-blog"
REGION="us-central1"

echo "🔐 Setting up secrets for Cloud Run..."
echo ""

# Load .env file
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
    echo "✅ Loaded .env file"
else
    echo "⚠️  No .env file found. Using defaults."
fi

# Create secrets in Secret Manager
echo "Creating secrets in Secret Manager..."

# Admin Password
echo -n "${ADMIN_PASSWORD}" | gcloud secrets create admin-password --data-file=- --replication-policy=automatic 2>/dev/null || \
echo -n "${ADMIN_PASSWORD}" | gcloud secrets versions add admin-password --data-file=-

# Secret Key
echo -n "${SECRET_KEY}" | gcloud secrets create secret-key --data-file=- --replication-policy=automatic 2>/dev/null || \
echo -n "${SECRET_KEY}" | gcloud secrets versions add secret-key --data-file=-

# GCS Credentials
if [ -f ../credentials.json ]; then
    gcloud secrets create gcs-credentials --data-file=../credentials.json --replication-policy=automatic 2>/dev/null || \
    gcloud secrets versions add gcs-credentials --data-file=../credentials.json
    echo "✅ Uploaded credentials.json"
else
    echo "⚠️  credentials.json not found. Please upload manually."
fi

# Grant Cloud Run service account access to secrets
SERVICE_ACCOUNT=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null)

if [ -z "$SERVICE_ACCOUNT" ]; then
    SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
fi

echo "Granting access to service account: ${SERVICE_ACCOUNT}"

gcloud secrets add-iam-policy-binding admin-password \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding secret-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gcs-credentials \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

echo ""
echo "✅ Secrets configured!"
echo ""
echo "📝 Update your deployment to use secrets:"
echo "   gcloud run services update ${SERVICE_NAME} \\"
echo "     --update-secrets=ADMIN_PASSWORD=admin-password:latest \\"
echo "     --update-secrets=SECRET_KEY=secret-key:latest \\"
echo "     --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=gcs-credentials:latest \\"
echo "     --region ${REGION}"
