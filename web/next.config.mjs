// MY CUVAS — Next.js frontend (migration Slices 0–1).
//
// The Flask backend stays the single source of truth. The browser
// only ever talks to THIS origin (see ../nextjs-migration-plan.md
// §2.1 / §2.2):
//
//  - /api/v1/* is proxied server-side to Flask (beforeFiles), so the
//    Flask session cookie is set and sent as a first-party cookie —
//    no CORS, no tokens.
//  - Every other path that the Next app does not itself serve is
//    proxied to Flask by the FALLBACK rewrite: legacy pages (admin
//    CRUD, student portal, PDFs, Excel…) keep working on this origin
//    until their migration slice lands. Fallback rewrites only fire
//    when no Next route or static asset matches, so the Next pages
//    (/login, /dashboard) and /_next/* assets are never proxied.
const FLASK_API_BASE = process.env.FLASK_API_BASE || "http://localhost:5055";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/v1/:path*",
          destination: `${FLASK_API_BASE}/api/v1/:path*`,
        },
      ],
      afterFiles: [],
      fallback: [
        {
          source: "/:path*",
          destination: `${FLASK_API_BASE}/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
