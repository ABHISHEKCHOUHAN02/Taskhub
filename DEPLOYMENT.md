# TaskHub Deployment Guide

This project is split into a Next.js frontend and a Flask API/worker backend.

## Recommended Hosting

- Frontend: Vercel, root directory `frontend`
- Backend API: Render web service, root directory `backend`
- Worker: Render background worker, root directory `backend`
- Database and storage: Supabase
- Queue: managed Redis
- Email: Resend

## 1. Prepare External Services

1. Create a Supabase project.
2. Create the Supabase Storage bucket named in `SUPABASE_STORAGE_BUCKET`.
3. Create a managed Redis instance.
4. Create a Resend API key.
5. Verify a sender domain or subdomain in Resend.
6. Create Google and GitHub OAuth apps.

Resend note: if the Resend account is still in test mode or the sender domain is not verified, emails can be limited to the Resend account email or test recipients. To send assignment emails to a senior/reviewer, verify a real domain in Resend and use that domain in `EMAIL_FROM`.

## 2. Deploy Backend API On Render

Create a Render web service:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app`

Set these environment variables:

```env
FLASK_ENV=production
DATABASE_URL=postgresql://postgres:<password>@<supabase-host>:5432/postgres?sslmode=require
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_STORAGE_BUCKET=taskhub-assets
REDIS_URL=<managed-redis-url>
FRONTEND_URL=https://<vercel-app-url>
FLASK_SECRET_KEY=<long-random-secret>
GOOGLE_CLIENT_ID=<google-client-id>
GOOGLE_CLIENT_SECRET=<google-client-secret>
GOOGLE_REDIRECT_URI=https://<vercel-app-url>/api/auth/oauth/google/callback
GITHUB_CLIENT_ID=<github-client-id>
GITHUB_CLIENT_SECRET=<github-client-secret>
GITHUB_REDIRECT_URI=https://<vercel-app-url>/api/auth/oauth/github/callback
ADMIN_EMAILS=<your-admin-email>
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_DOMAIN=
RESEND_API_KEY=<resend-api-key>
EMAIL_FROM=TaskHub <no-reply@verified-domain.com>
AI_PROVIDER=huggingface
HF_TOKEN=<hugging-face-token>
HF_PROVIDER=hf-inference
HF_MODEL_ID=black-forest-labs/FLUX.1-Kontext-dev
CORS_ORIGINS=https://<vercel-app-url>
```

Run the database migration from the backend environment once:

```bash
flask --app wsgi:app db upgrade
```

## 3. Deploy Worker On Render

Create a Render background worker:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `celery -A worker:celery worker -l info`

Use the same backend environment variables. The worker needs `DATABASE_URL`, `SUPABASE_*`, `REDIS_URL`, `RESEND_API_KEY`, `EMAIL_FROM`, and AI provider keys.

## 4. Deploy Frontend On Vercel

Create a Vercel project:

- Root directory: `frontend`
- Build command: `npm run build`
- Install command: `npm install`

Set these environment variables:

```env
NEXT_PUBLIC_APP_URL=https://<vercel-app-url>
NEXT_PUBLIC_API_BASE_URL=https://<render-api-url>
API_BASE_URL=https://<render-api-url>
```

The frontend rewrites `/api/*` requests to the Flask backend, so OAuth callback URLs can remain on the frontend domain.

## 5. Configure OAuth Callback URLs

Google OAuth redirect URI:

```text
https://<vercel-app-url>/api/auth/oauth/google/callback
```

GitHub OAuth callback URL:

```text
https://<vercel-app-url>/api/auth/oauth/github/callback
```

These must match `GOOGLE_REDIRECT_URI` and `GITHUB_REDIRECT_URI` exactly.

## 6. Reviewer Login Flow

The app currently supports Google/GitHub OAuth login, not email/password login.

Recommended assignment flow:

1. Set your email in `ADMIN_EMAILS`.
2. Log in first with that admin email.
3. Ask the senior/reviewer to log in with Google or GitHub.
4. Their first OAuth login creates a normal user account.
5. Assign a task to the reviewer from the admin dashboard.
6. The reviewer receives task notification emails only after Resend sender-domain verification is complete.

If the first person to log in is not you, the backend may make that first OAuth user an admin because no admin exists yet. Avoid that by setting `ADMIN_EMAILS` before the first production login.

## 7. Final Checks

Run these before sharing the assignment:

```bash
cd frontend
npm run lint
npm run build
```

Then verify manually:

- Home page has no direct Google/GitHub buttons.
- `/login` and `/register` still allow Google/GitHub OAuth.
- Admin users redirect to `/admin`.
- Normal users redirect to `/dashboard`.
- Admin can create and assign a task.
- User can generate all 8 images and submit.
- Resend sends emails to external recipients from the verified sender domain.
