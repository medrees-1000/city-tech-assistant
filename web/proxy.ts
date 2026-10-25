// The page calls /api/ask and /api/feedback on its own origin. This proxy forwards those two paths
// to the API (API_URL) and adds the shared secret, the visitor address and the Clerk user id
// (lib/forward.ts), so the browser never talks to the API host: no CORS, no mixed content.
// /api/ask needs a signed-in visitor with a verified Gmail address (gateUser); /api/feedback is open.
// Clerk's helper runs on both paths so the session is read; it blocks nothing by itself.
import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { apiTarget, forwardHeaders, gateFor } from "./lib/forward.ts";

export default clerkMiddleware(async (auth, request) => {
  const { pathname, search } = request.nextUrl;
  const session = await auth(); // claims come from the session token: no Clerk call per request
  const gate = gateFor(pathname, session.userId, session.sessionClaims as Record<string, unknown> | null);
  if (gate === "sign_in_required") return NextResponse.json({ error: gate }, { status: 401 });
  if (gate === "gmail_required") return NextResponse.json({ error: gate }, { status: 403 });
  const userId = pathname === "/api/ask" ? session.userId : null; // feedback carries no user id
  const target = apiTarget(pathname, search, process.env.API_URL);
  const headers = forwardHeaders(request.headers, process.env.CTA_PROXY_SECRET, userId);
  return NextResponse.rewrite(target, { request: { headers } });
});

export const config = { matcher: ["/api/ask", "/api/feedback"] };
