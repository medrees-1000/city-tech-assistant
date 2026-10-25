// What the page's proxy (proxy.ts) sends to the API. Plain functions, so they can be tested.
// The API trusts the visitor address in x-real-ip only when x-cta-proxy-secret matches its own
// CTA_PROXY_SECRET (src/cta/api/guard.py). Vercel documents that it overwrites x-forwarded-for with the
// visitor's address "to prevent IP spoofing" (https://vercel.com/docs/headers/request-headers), so that
// header is read first; x-real-ip is only the fallback (the local rehearsal has no Vercel in front).

export const PROXY_HEADER = "x-cta-proxy-secret";
export const REAL_IP_HEADER = "x-real-ip";
// A header of our own: Vercel may replace x-real-ip on the hop to the API, but not a custom header.
export const VISITOR_HEADER = "x-cta-visitor";
// The Clerk user id (opaque, "user_..."), set by the proxy only for a signed-in Gmail visitor; never the email.
export const USER_HEADER = "x-cta-user";

// Who may ask: the verified primary email must end with @ + one of these (lowercase, exact match, so
// googlemail.com is not allowed). Adding a domain later is one line here plus a test.
export const ALLOWED_EMAIL_DOMAINS = ["gmail.com"];

export type Gate = "allowed" | "sign_in_required" | "gmail_required";

/** The gate for one path: only /api/ask needs a login; /api/feedback is open. */
export function gateFor(pathname: string, userId: string | null | undefined, claims: Record<string, unknown> | null | undefined): Gate {
  return pathname === "/api/ask" ? gateUser(userId, claims) : "allowed";
}

/** The login decision from the Clerk user id and the session claims (email, email_verified, set in the
 * Clerk dashboard). A missing or odd claim means "not allowed", never an error. */
export function gateUser(userId: string | null | undefined, claims: Record<string, unknown> | null | undefined): Gate {
  if (!userId) return "sign_in_required";
  const email = claims?.email;
  const verified = claims?.email_verified;
  if (typeof email !== "string" || (verified !== true && verified !== "true")) return "gmail_required";
  const lower = email.toLowerCase();
  const at = lower.lastIndexOf("@");
  const domain = lower.slice(at + 1);
  return at > 0 && ALLOWED_EMAIL_DOMAINS.includes(domain) ? "allowed" : "gmail_required";
}

/** The visitor's address as the host reports it: the first x-forwarded-for entry, else x-real-ip. */
export function visitorAddress(incoming: Headers): string | null {
  const first = incoming.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (first) return first;
  return incoming.get(REAL_IP_HEADER)?.trim() || null;
}

/** The request headers for the API: the visitor's own copy, minus anything that would forge the
 * trusted headers or carry the login (cookie, authorization, x-clerk-*), plus the shared secret (when
 * one is configured), the visitor address and, for a signed-in visitor, the Clerk user id. */
export function forwardHeaders(incoming: Headers, secret: string | undefined, userId?: string | null): Headers {
  const out = new Headers(incoming);
  out.delete("cookie");
  out.delete("authorization");
  for (const name of [...out.keys()]) if (name.startsWith("x-clerk-")) out.delete(name);
  out.delete(USER_HEADER); // the proxy sets its own, from the session
  const address = visitorAddress(incoming);
  out.delete(PROXY_HEADER);
  out.delete(REAL_IP_HEADER);
  out.delete(VISITOR_HEADER); // always overwritten, never appended to or passed on from the client
  if (secret) {
    out.set(PROXY_HEADER, secret);
    if (userId) out.set(USER_HEADER, userId);
    if (address) {
      out.set(REAL_IP_HEADER, address);
      out.set(VISITOR_HEADER, address);
    }
  }
  return out;
}

/** Where /api/ask and /api/feedback go: the API origin with the /api prefix removed. */
export function apiTarget(pathname: string, search: string, apiUrl: string | undefined): URL {
  return new URL(pathname.replace(/^\/api/, "") + search, apiUrl || "http://127.0.0.1:8000");
}
