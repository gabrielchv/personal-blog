# 🚀 Deploy Your Blog to Google Cloud Run

## Prerequisites

1. **Google Cloud SDK** installed
   ```bash
   # Install gcloud CLI: https://cloud.google.com/sdk/docs/install
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   ```

2. **GCP Project** created
   - Go to https://console.cloud.google.com
   - Create a new project (or use existing)
   - Note your PROJECT_ID

3. **Billing enabled** on your project

## 📝 Step-by-Step Deployment

### 1. Configure Your Project

Edit `deploy.sh` and change:
```bash
PROJECT_ID="your-gcp-project-id"  # Change this to your actual project ID
```

### 2. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

### 3. Configure Environment Variables

Make sure your `.env` file (in parent directory) has:
```env
ADMIN_PASSWORD=your-strong-password
SECRET_KEY=random-secret-key-here
GCS_BUCKET_NAME=blog-posts-gazerah
GCS_SERVICE_ACCOUNT_KEY_PATH=../credentials.json
```

### 4. Deploy!

From the `blog-site` directory:
```bash
cd blog-site
./deploy.sh
```

This will:
- ✅ Build your Docker image
- ✅ Push to Google Container Registry
- ✅ Deploy to Cloud Run
- ✅ Give you a public URL

### 5. Set Up Secrets (IMPORTANT!)

After first deployment:
```bash
./setup-secrets.sh
```

This uploads your credentials and passwords securely to Google Secret Manager.

## 🔧 Manual Configuration

### Option 1: Environment Variables (Simple, less secure)

In Cloud Run console:
1. Go to your service
2. Click "Edit & Deploy New Revision"
3. Under "Variables & Secrets" tab
4. Add:
   - `ADMIN_PASSWORD` = your password
   - `SECRET_KEY` = random string
   - `GCS_BUCKET_NAME` = your bucket name

### Option 2: Secret Manager (Recommended, more secure)

Already done if you ran `setup-secrets.sh`!

## 📊 Monitoring & Logs

View logs:
```bash
gcloud run services logs read personal-blog --region=us-central1
```

View service details:
```bash
gcloud run services describe personal-blog --region=us-central1
```

## 💰 Cost Estimation

Cloud Run pricing (approximate):
- **Free tier**: 2M requests/month, 360k GB-seconds
- **After free tier**: ~$0.40 per 1M requests
- **Your blog** (low traffic): ~$5-10/month
- **Scales to zero** when not in use!

## 🔄 Updating Your Blog

After making changes:
```bash
cd blog-site
./deploy.sh
```

It will redeploy automatically!

## 🐛 Troubleshooting

### "Permission denied" errors
```bash
gcloud auth login
gcloud auth application-default login
```

### "Service account doesn't have storage permissions"
```bash
# Grant storage permissions to Cloud Run service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/storage.admin"
```

### "FFmpeg not found"
- Already included in Dockerfile, should work!

### Check logs
```bash
gcloud run services logs read personal-blog --region=us-central1 --limit=50
```

## 🌐 Custom Domain (Optional)

1. In Cloud Run console, go to "Manage Custom Domains"
2. Add your domain
3. Update DNS with provided records
4. SSL is automatic!

## 📱 Access Your Blog

- **Public blog**: https://your-service-url.run.app
- **Admin panel**: https://your-service-url.run.app/admin
- **Login**: Use password from `.env`

Enjoy your deployed blog! 🎉
