# Backend

Flask API and worker configuration live here.

## Environment

Use `backend/.env.example` as the source of truth for backend-only runtime values. The backend reads the shared app database and storage settings from the same contract as the rest of the workspace:

- `DATABASE_URL` for Supabase Postgres
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for storage operations
- `SUPABASE_STORAGE_BUCKET` for generated and source images
- `REDIS_URL` for background jobs
- OAuth, email, and AI provider credentials
- `GOOGLE_REDIRECT_URI` and `GITHUB_REDIRECT_URI` should point to the Flask callback routes
- `SESSION_COOKIE_DOMAIN`, `SESSION_COOKIE_SECURE`, and `SESSION_COOKIE_SAMESITE` control browser session handling
- `ADMIN_EMAILS` can be used to seed the admin role by email
- If frontend and backend are deployed on sibling subdomains, set `SESSION_COOKIE_DOMAIN` to the shared parent domain so the browser sends the session cookies to both apps.

## Conventions

- REST API routes live under `/api/...`.
- Task statuses use snake_case values: `pending`, `assigned`, `in_progress`, `submitted`, `accepted`, `revision_requested`.
- Image types use stable keys such as `white_bg`, `theme_marble`, `creative_beach`, `model_front`, and `model_closeup`.
- Store timestamps in UTC and serialize them as ISO 8601 strings.
- Before database queries, set `app.user_id` and `app.user_role` on the PostgreSQL session so RLS can evaluate the active actor.
- Store Supabase Storage object paths under `tasks/<task_id>/...` and keep those references in the database rows.
- The image pipeline uses Hugging Face Inference Providers with `HF_TOKEN`, `HF_PROVIDER`, and `HF_MODEL_ID`.
- Auth routes:
  - `GET /api/auth/oauth/google/start`
  - `GET /api/auth/oauth/github/start`
  - `GET|POST /api/auth/oauth/google/callback`
  - `GET|POST /api/auth/oauth/github/callback`
  - `GET /api/auth/me`
  - `POST /api/auth/logout`
- Admin task routes:
  - `GET /api/admin/tasks`
  - `POST /api/admin/tasks`
  - `POST /api/admin/tasks/<task_id>/assign`
  - `POST /api/admin/tasks/<task_id>/accept`
  - `POST /api/admin/tasks/<task_id>/request-revision`
  - `DELETE /api/admin/tasks/<task_id>`
- User task routes:
  - `GET /api/tasks`
  - `GET /api/tasks/<task_id>`
  - `POST /api/tasks/<task_id>/start`
  - `POST /api/tasks/<task_id>/submit`
  - `GET /api/tasks/<task_id>/generations`
- Generation routes:
  - `POST /api/tasks/<task_id>/generations`
  - `POST /api/tasks/<task_id>/generate`
  - `GET /api/generation-jobs/<job_id>`
  - `GET /api/jobs/<job_id>/status`
  - `POST /api/tasks/<task_id>/generations/<generation_id>/mark-final`
  - `DELETE /api/tasks/<task_id>/generations/<generation_id>`
  - `DELETE /api/generations/<generation_id>`
- Task state changes create `audit_logs` records. Assignment, submission, acceptance, and revision-request actions trigger Resend emails when `RESEND_API_KEY` is configured.
- Task submission is blocked until all 8 required generation variants exist and each one is marked final.

## Frontend Contract

The Next.js app consumes the backend through SSR fetches and expects these convenience endpoints to stay stable:

- `/api/my-tasks`
- `/api/admin/tasks`
- `/api/admin/users`
- `/api/tasks/<task_id>`
- `/api/tasks/<task_id>/generations`
- `/api/tasks/<task_id>/audit-logs`
- `/api/jobs/<job_id>/status`

These routes are compatibility aliases around the existing Flask implementation so the frontend can stay aligned with the PDF route naming without forcing a rewrite.

## Migration Commands

Run these from `backend/` after setting `DATABASE_URL`:

```bash
flask --app wsgi:app db init
flask --app wsgi:app db migrate -m "initial schema"
flask --app wsgi:app db upgrade
```

If the migration folder already exists, skip `db init` and run:

```bash
flask --app wsgi:app db migrate -m "initial schema"
flask --app wsgi:app db upgrade
```

## Notes

- The repository now uses Flask-Migrate as the single migration path.
- The old SQL-only migration files were removed to avoid drift between two schemas.
- Run the API with `flask --app wsgi:app run` and the worker with `celery -A worker:celery worker -l info` from `backend/`.
