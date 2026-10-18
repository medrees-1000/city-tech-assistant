// The page calls /api/ask and /api/feedback on its own origin. This proxy forwards those two paths
// to the API (API_URL) and adds the shared secret and the visitor address (lib/forward.ts), so the
// browser never talks to the API host: no CORS, no mixed content. Anything else under /api is a 404.
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { apiTarget, forwardHeaders } from "./lib/forward.ts";

export function proxy(request: NextRequest) {
  const target = apiTarget(request.nextUrl.pathname, request.nextUrl.search, process.env.API_URL);
  const headers = forwardHeaders(request.headers, process.env.CTA_PROXY_SECRET);
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = { matcher: ["/api/ask", "/api/feedback"] };
