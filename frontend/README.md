# Frontend

TaskHub Next.js app with:

- public landing page
- SSR admin dashboard
- SSR user dashboard
- SSR task detail page with AI studio controls
- role-cookie redirects for protected routes
- dark/light toggle

## Environment

Use `frontend/.env.example` for public runtime values only:

- `NEXT_PUBLIC_APP_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_STORAGE_BUCKET`

Do not place secrets in frontend env files.

## Local Development

Run the app from this folder after the backend is available:

```bash
npm run dev
```

The UI expects the Flask API to be reachable at `NEXT_PUBLIC_API_BASE_URL` and reuses the backend auth cookies for SSR fetches.

## Routes

- `/` public landing page
- `/login` and `/register` auth entry points
- `/dashboard` user task queue
- `/admin` admin task console
- `/tasks/[task_id]` AI studio and submission view

## Data Flow

- Server components fetch live data from Flask during SSR.
- Auth state is checked with the current session cookie plus `/api/auth/me`.
- Admin/user redirects stay aligned with the backend role cookie.
- Task generation actions call the Flask compatibility routes under `/api/...`.

## Conventions

- Keep all authenticated API calls under the shared `/api` contract.
- Use ISO 8601 UTC timestamps in responses.
- Use the same task-status and image-type keys documented in the root README and backend README.
- Keep layout changes backward-compatible with the existing role-cookie redirect model.
