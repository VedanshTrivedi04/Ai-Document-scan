# FDDT — Fraud Document Detection Tool — Frontend

React + TypeScript (Vite), shadcn-style UI components (Radix + Tailwind),
TanStack Query, React Hook Form + Zod, React Router, react-pdf. See
[`../docs/frontend/screens.md`](../docs/frontend/screens.md) and
[`../docs/frontend/components.md`](../docs/frontend/components.md) for the
screens and shared components.

**Screens:** login, dashboard, case queue, my cases, new case / upload, case
detail (live processing status, PDF overlays, risk reasons, audit timeline,
report export), audit history, and admin settings (issuer registry, risk
rules, users).

## Setup

The backend (`../backend`) must be running first — see the root README.
Postgres/Redis: `docker compose up -d` from the repo root.

```bash
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api/*` to
`http://127.0.0.1:8000` (see `vite.config.ts`), so no backend CORS setup
is needed locally.

### Organisation Subdomains (Local Development)

Each organisation has its own subdomain. Browsers automatically resolve `*.localhost`
to the local machine (127.0.0.1).

- Run the dev server (`npm run dev`) and open `http://<subdomain>.localhost:5173` (e.g. `http://indore.localhost:5173`).
- Set `VITE_APP_BASE_DOMAIN=localhost` in `.env` (or pass it in your shell environment).
- Vite allows `*.localhost` via `server.allowedHosts: ['.localhost']` in `vite.config.ts`.
- Sign-in on an organisation's subdomain is scoped to that organisation's users. Signing in on the platform site (`http://localhost:5173`) offers redirection to the organisation's site.

Seeded test login (from `backend/seed.py`): `admin@example.com` /
`ChangeMe123!`.

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — type-check (`tsc -b`) + production build
- `npm run lint` — oxlint
