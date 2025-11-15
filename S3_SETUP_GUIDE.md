# S3 Setup Guide for Invoice Storage

This guide walks you through setting up an S3 bucket with a dedicated IAM user for secure invoice storage on Railway.

## Step 1: Create S3 Bucket

1. **Go to AWS Console** → S3 → Create bucket

2. **Bucket Settings:**
   - **Bucket name**: `invoice-handler-[your-name]` (must be globally unique)
   - **Region**: `us-east-1` (or your preferred region)
   - **Block Public Access**: ✅ **Block ALL public access** (keep invoices private)
   - **Bucket Versioning**: Optional (recommended for data protection)
   - **Encryption**: Enable (SSE-S3 is fine)

3. **Click "Create bucket"**

## Step 2: Configure CORS

CORS is needed so browsers can directly access presigned URLs.

1. Go to your bucket → **Permissions** tab → **CORS**
2. Click "Edit" and paste:

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:5173",
      "https://your-production-domain.com"
    ],
    "AllowedMethods": [
      "GET",
      "PUT",
      "POST"
    ],
    "AllowedHeaders": [
      "*"
    ],
    "ExposeHeaders": [
      "ETag"
    ],
    "MaxAgeSeconds": 3000
  }
]
```

**Note:** Update `AllowedOrigins` with your actual frontend URLs when deploying to production.

## Step 3: Create IAM User for the Application

### 3.1 Create User

1. **Go to AWS Console** → IAM → Users → **Create user**
2. **User name**: `invoice-handler-railway`
3. **Access type**: Leave unchecked (no console access needed)
4. Click **Next**

### 3.2 Create Custom Policy

1. Click **"Attach policies directly"**
2. Click **"Create policy"**
3. Switch to **JSON** tab
4. Paste this policy (replace `YOUR_BUCKET_NAME` with your actual bucket name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
    },
    {
      "Sid": "ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }
  ]
}
```

5. Click **Next**
6. **Policy name**: `InvoiceHandlerS3Access`
7. Click **Create policy**

### 3.3 Attach Policy to User

1. Go back to the user creation tab
2. Refresh the policy list
3. Search for `InvoiceHandlerS3Access`
4. Check the box next to it
5. Click **Next**
6. Click **Create user**

### 3.4 Generate Access Keys

1. Click on the newly created user (`invoice-handler-railway`)
2. Go to **"Security credentials"** tab
3. Scroll to **"Access keys"**
4. Click **"Create access key"**
5. Select **"Application running outside AWS"**
6. Click **Next**
7. (Optional) Add description: "Invoice Handler Railway"
8. Click **"Create access key"**
9. **⚠️ IMPORTANT**: Copy both keys immediately:
   - **Access key ID**: `AKIA...`
   - **Secret access key**: `...` (won't be shown again!)

## Step 4: Configure Application

### For Local Development

Add to your `.env` file:

```env
# S3 Configuration
S3_BUCKET=invoice-handler-your-name
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### For Railway Deployment

1. Go to your Railway project
2. Click on your backend service
3. Go to **"Variables"** tab
4. Add these environment variables:

```
S3_BUCKET=invoice-handler-your-name
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

## Step 5: Test the Setup

### Test Upload

```bash
curl -X POST "http://localhost:8000/upload/presigned-url?filename=test.pdf"
```

Should return a presigned POST URL with fields.

### Test View

1. Upload a file to S3 (via presigned URL or AWS console)
2. Test viewing:

```bash
curl "http://localhost:8000/file/view?path=s3://YOUR_BUCKET/uploads/test.pdf"
```

Should return a presigned GET URL.

## Security Best Practices

### ✅ What We Did Right

- **Private bucket** - No public access
- **Dedicated IAM user** - Not using root/personal account
- **Least privilege** - User only has S3 access to one bucket
- **Presigned URLs** - Time-limited access (1 hour expiry)
- **CORS configured** - Browser can access presigned URLs

### 🔒 Additional Recommendations

1. **Enable S3 Bucket Versioning**
   - Protects against accidental deletions
   - Can recover previous versions

2. **Enable Logging**
   - Track all S3 access
   - Useful for auditing

3. **Set up Lifecycle Rules**
   - Auto-delete old invoices after X years (if allowed by regulations)
   - Move to Glacier for long-term archival

4. **Rotate Access Keys Regularly**
   - Rotate every 90 days
   - Railway makes this easy with environment variable updates

5. **Monitor Costs**
   - Set up AWS budgets/alerts
   - S3 storage is cheap (~$0.023/GB/month)
   - Data transfer OUT is more expensive (~$0.09/GB)

## Troubleshooting

### "Access Denied" Errors

1. Check IAM policy has correct bucket name
2. Verify environment variables are set
3. Check CORS configuration
4. Ensure bucket name matches in all configs

### CORS Errors in Browser

1. Verify CORS policy includes your frontend URL
2. Check for typos in AllowedOrigins
3. Clear browser cache
4. Check browser console for specific CORS error

### Presigned URL Expires Too Quickly

Edit `main.py` line ~144:

```python
ExpiresIn=3600  # 1 hour, increase if needed
```

## Cost Estimate

For a small business processing 100 invoices/month:

- **Storage**: 100 files × 200KB = 20MB = **$0.0005/month**
- **Requests**: 200 GET + 100 PUT = **$0.0001/month**
- **Data transfer**: Negligible for viewing

**Total: ~$0.01/month** (essentially free!)

## Next Steps

- [ ] Set up automated backups to another region
- [ ] Implement invoice retention policy
- [ ] Add CloudFront if you need better global performance
- [ ] Set up S3 event notifications for file uploads (future feature)


