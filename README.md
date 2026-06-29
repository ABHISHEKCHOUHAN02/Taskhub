# TaskHub

TaskHub is a full-stack task management platform with an AI-assisted product photography workflow.

## Stack

- Frontend: Next.js + TypeScript
- Backend: Flask API and background worker
- Database: Supabase Postgres
- File storage: Supabase Storage
- Jobs: managed Redis
- Email: Resend

## Environment Contract

The canonical environment template is [`/.env.example`](./.env.example).

- `backend/.env.example` contains backend-only secrets and server settings.
- `frontend/.env.example` contains public browser-safe values only.
- Keep secrets out of frontend env files.
- Use Supabase for database access and file storage.
- Use Redis only for background job processing.
- `GOOGLE_REDIRECT_URI` should point at the Flask OAuth callback route.
- The backend must set `app.user_id` and `app.user_role` on the database session before it runs any tenant-aware queries so RLS can evaluate the current actor.
- Store Supabase Storage objects under `tasks/<task_id>/...` so database rows and storage policies can resolve the owning task cleanly.

## Repo Conventions

- API routes live under `/api/...`.
- Task statuses use snake_case values: `pending`, `assigned`, `in_progress`, `submitted`, `accepted`, `revision_requested`.
- Image type keys stay stable across backend, frontend, and worker code: `white_bg`, `theme_marble`, `theme_velvet`, `creative_beach`, `creative_studio`, `model_front`, `model_side`, `model_closeup`.
- Store timestamps in UTC and serialize them as ISO 8601 strings.
- Do not commit runtime secrets, local caches, build output, or generated uploads.
- The live image-generation path uses Hugging Face Inference Providers with `HF_TOKEN`, `HF_PROVIDER`, and `HF_MODEL_ID`.
- Task submission is gated until all 8 required generated images exist and are marked final.

## Local Setup

1. Create the Supabase project and storage bucket.
2. Provision a managed Redis instance.
3. Copy the env example files into local `.env` files.
4. Run Flask-Migrate from the backend once the models are in place.
5. Run the backend API and the frontend app against the hosted services.

## Migrations

The repo uses Flask-Migrate as the active migration path. Generate and apply migrations from `backend/` against the Supabase `DATABASE_URL`.

The database schema should be treated as the Flask model layer plus Alembic migration history. Supabase-specific policies will be added as the backend grows, using the same migration system unless a separate SQL-only step is explicitly required later.

## Deployment

- Frontend: Vercel or a similar static/SSR host.
- Backend: Render, Railway, or another Flask-capable host.
- Worker: same backend platform or a separate process with the same env contract.
- Supabase handles the database and file storage.
- Redis is external and managed.
- Generation jobs run asynchronously through Celery and Redis, then store the completed image in Supabase Storage.
- See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for the assignment handoff setup, reviewer login flow, and Resend sender-domain notes.

## Sample Artifacts

The `generated_samples/` folder is reserved for the 8 evaluation images required by the assignment, plus a short README describing each variation.

## Frontend Completion

- The Next.js app now exposes a public landing page, SSR admin dashboard, SSR user dashboard, and a task detail AI studio.
- The frontend fetches live data from Flask during SSR and keeps the existing role-cookie redirect model.
- The task detail page enforces the full 8-image workflow before submission.

## Assumption Note

The PDF route names are handled as Flask compatibility aliases over the existing backend flow so the implementation stays backward-compatible while still matching the evaluator-facing URLs.
