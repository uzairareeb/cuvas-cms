# MY CUVAS — Next.js frontend (`web/`)

The Next.js + React + TypeScript + Tailwind CSS + shadcn/ui frontend
for MY CUVAS, built incrementally over the existing Flask backend
(see `../nextjs-migration-plan.md`). **Slice 1 state:** login page,
app shell (navy sidebar + topbar) and a read-only admin dashboard
are live in this codebase. The Flask app in `../app/` remains the
live system and the single source of truth throughout the migration.

## Routes in this app

| Route | What it is |
|---|---|
| `/` | Redirects to `/dashboard`. |
| `/login` | Sign-in form → `POST /api/v1/auth/login`. Admins land on `/dashboard`; other roles are sent (full page load) to their legacy home path from the API response. Already-signed-in visitors are routed the same way via `GET /api/v1/auth/me`. API error messages (including the account-locked text) are shown verbatim. |
| `/dashboard` | Admin-only shell + dashboard. Guarded client-side via `/api/v1/auth/me` (401 → `/login`; non-admin → legacy home), data from `GET /api/v1/admin/dashboard`. KPI cards, students-by-program/session bars, pending approvals (click → legacy queue page), pending vouchers, recent students, notifications, recent activity, quick links — all real API data, nothing invented. |
| everything else | **Not a Next page** — proxied to Flask by the fallback rewrite (below), so the legacy UI keeps working on this origin. |

## How the pieces fit

- The browser only ever talks to this project's origin.
  `next.config.mjs` rewrites (object form):
  - `beforeFiles`: `/api/v1/*` → `FLASK_API_BASE` (the JSON API).
  - `fallback`: `/:path*` → `FLASK_API_BASE` — fires only when no
    Next route or static asset matches, so `/login`, `/dashboard`
    and `/_next/*` are never proxied, while every legacy path
    (admin CRUD, student portal, PDFs, Excel…) is served by Flask
    under this origin.
- Because of the proxy, the Flask session cookie is set and sent
  first-party — no CORS, no tokens, no secrets in frontend code.
  All API calls go through `src/lib/api.ts`, which always sends
  `X-Requested-With: XMLHttpRequest` (Flask's API CSRF guard) and
  unwraps the `{ok, data, error}` envelope into a typed `ApiError`.

## Design system

- **Palette (decided by the user for this frontend, 2026-10-24):**
  navy / white / subtle gold. Anchors: primary navy `#17365D`,
  deep sidebar navy `#0F2B4C`, secondary blue `#2457A7`, gold
  accent `#E7B34C` (active indicators, highlights), background
  `#F4F7FB`, surface `#FFFFFF`, text `#1E293B`, muted `#64748B`,
  border `#E2E8F0`, plus success `#15803D` / warning `#B45309` /
  error `#DC2626`. All values live as CSS variables in
  `src/app/globals.css` (brand hex tokens + shadcn HSL channels)
  and are mapped to Tailwind names in `tailwind.config.ts` — the
  theme is edited in one place only.
- **Font:** Inter via `next/font/google` (falls back to the system
  stack in `globals.css` if the font cannot be fetched).
- **Brand:** "MY CUVAS" + "University Management System". The
  official CUVAS logo is used exactly as supplied: it is embedded as
  a base64 data URI in `src/lib/logo.ts` (the GitHub connector
  cannot push binary files) and shown on the login card and in the
  sidebar header with its natural aspect preserved — never redrawn,
  recoloured or cropped.
- **Components:** shadcn/ui copy-in components under
  `src/components/ui/` (`button`, `input`, `label`, `card`) using
  the installed cva / clsx / tailwind-merge / Radix primitives;
  the shell lives in `src/components/shell/Shell.tsx` (Lucide icons
  + text labels, gold active state, sidebar collapses to a top bar
  with a slide-over menu under `lg`).

## Run locally

```bash
cd web
npm install
FLASK_API_BASE=http://localhost:5055 npm run dev   # Flask app runs on :5055
```

`FLASK_API_BASE` defaults to `http://localhost:5055` when unset.
Production smoke test: `npm run build`, then
`FLASK_API_BASE=http://localhost:5055 npm start`.

Verified for Slice 1: `npm run build` passes, and a live local
end-to-end (Flask on :5055 with a fresh seeded DB + this app on
:3100) passed — admin login through the Next origin, `/dashboard`
and its API data (the seeded figures), a legacy page
(`/admin/students`) proxied from Flask, the student-role 403 and
the anonymous 401 on the dashboard API.

## Deployment

This folder gets its **own Vercel project** (project root directory
= `web`) — separate from the existing Flask project, which is not
restructured. Set `FLASK_API_BASE` on the Vercel project to the
Flask deployment's URL (server-side only; it is a rewrite target,
never shipped to the browser as data). The main domain moves to
this project only at the cutover slice (Slice 8).

## House rules

- `node_modules/` and `.next/` are never committed (see `.gitignore`).
- No URLs, keys or credentials in frontend code — relative `/api/v1`
  paths only, via `src/lib/api.ts`.
- No invented data: every number on a page comes from the API.
