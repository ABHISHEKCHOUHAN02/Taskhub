# Frontend

Next.js app for the public landing page, admin dashboard, user dashboard, and task detail screens.

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

The UI expects the backend API to be reachable at `NEXT_PUBLIC_API_BASE_URL`.

## Conventions

- Keep all authenticated API calls under the shared `/api` contract.
- Use ISO 8601 UTC timestamps in responses.
- Use the same task-status and image-type keys documented in the root README and backend README.
