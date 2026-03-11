# Deployment Guide - Free Hosting

This guide shows how to deploy your FHIR web application for free using Render.

## Prerequisites

1. GitHub account (free)
2. Render account (free) - https://render.com
3. Your code pushed to GitHub

## Step 1: Push to GitHub

```bash
cd /Users/mike-nacey/Desktop/fhir_web
git init
git add .
git commit -m "Initial commit"
gh repo create fhir-web --public --source=. --push
# Or manually create repo on GitHub and push
```

## Step 2: Deploy Backend on Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `fhir-web-backend`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install uv && uv pip install --system .`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free

5. **Add Environment Variables** (click "Environment"):
   ```
   FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/
   EPIC_BACKEND_SERVICES_ENABLED=true
   EPIC_CLIENT_ID=f42e0c16-8c32-4e38-850b-a2bfd4172c62
   EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
   EPIC_PRIVATE_KEY_PATH=./keys/private_key.pem
   EPIC_KEY_ID=epic-backend-services-key
   EPIC_SCOPES=system/Patient.read system/Encounter.read system/ServiceRequest.read system/MedicationRequest.read
   EPIC_JWT_ALGORITHM=RS384
   CORS_ORIGINS=https://your-frontend-url.onrender.com
   ```

6. **Upload Private Key**:
   - Option A: Add as environment variable `EPIC_PRIVATE_KEY` (entire PEM content)
   - Option B: Commit keys/ folder to private GitHub repo (NOT recommended for production)

7. Click **"Create Web Service"**

8. **Note the URL**: e.g., `https://fhir-web-backend.onrender.com`

## Step 3: Deploy Frontend on Render

1. Click **"New +"** → **"Static Site"**
2. Connect same GitHub repository
3. Configure:
   - **Name**: `fhir-web-frontend`
   - **Branch**: `main`
   - **Root Directory**: `frontend/frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`

4. **Add Environment Variable**:
   ```
   VITE_API_BASE_URL=https://fhir-web-backend.onrender.com
   ```

5. Click **"Create Static Site"**

6. **Note the URL**: e.g., `https://fhir-web-frontend.onrender.com`

## Step 4: Update CORS

1. Go back to backend service settings
2. Update `CORS_ORIGINS` environment variable with frontend URL:
   ```
   CORS_ORIGINS=https://fhir-web-frontend.onrender.com
   ```

## Alternative: Vercel (Frontend) + Render (Backend)

### Frontend on Vercel (Better Performance)

1. Go to https://vercel.com
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repository
4. Configure:
   - **Root Directory**: `frontend/frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Environment Variables**:
     ```
     VITE_API_BASE_URL=https://fhir-web-backend.onrender.com
     ```

5. Click **"Deploy"**

**Pros**: Vercel frontend is faster and doesn't sleep
**Your URL**: `https://your-app.vercel.app`

## Important Notes

### Free Tier Limitations

**Render Free Tier:**
- Backend sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- 750 hours/month free (enough for demo purposes)

**Vercel Free Tier:**
- No sleep, instant responses
- 100GB bandwidth/month
- Perfect for demos

### Private Key Security

For production, use one of these:
1. **Render Secret Files**: Upload private key as a secret file
2. **Environment Variable**: Store entire PEM content in env var and modify code to read from it
3. **Secrets Manager**: AWS Secrets Manager, etc.

### Quick Demo Hack

To quickly get the private key working, modify `backend/app/dependencies.py`:

```python
# Read from environment variable if path doesn't exist
private_key_path = settings.epic_private_key_path
if not os.path.exists(private_key_path):
    # Try reading from environment variable
    private_key = os.getenv("EPIC_PRIVATE_KEY", "")
else:
    with open(private_key_path, "r") as f:
        private_key = f.read()
```

Then set `EPIC_PRIVATE_KEY` environment variable with the entire PEM content.

## Testing Your Deployment

1. Visit your frontend URL
2. Try searching for "Smith"
3. Click on a patient to view details
4. Verify encounters and orders load

## Troubleshooting

**Backend not starting:**
- Check build logs in Render dashboard
- Verify all environment variables are set
- Check that FHIR library is installed properly

**Frontend can't connect to backend:**
- Verify CORS_ORIGINS includes frontend URL
- Check VITE_API_BASE_URL is correct
- Look at browser console for errors

**First load is slow:**
- Normal on Render free tier (service waking up)
- Consider Vercel for frontend to avoid this

## Estimated Setup Time

- Total: 15-30 minutes
- Backend: 10-15 minutes
- Frontend: 5-10 minutes
- Testing: 5 minutes

## Cost

**100% FREE** for demo purposes! Perfect for showing your boss.
