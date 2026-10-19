// What the page's proxy (proxy.ts) sends to the API. Plain functions, so they can be tested.
// The API trusts the visitor address in x-real-ip only when x-cta-proxy-secret matches its own
// CTA_PROXY_SECRET (src/cta/api/guard.py). Vercel documents that it overwrites x-forwarded-for with the
// visitor's address "to prevent IP spoofing" (https://vercel.com/docs/headers/request-headers), so that
// header is read first; x-real-ip is only the fallback (the local rehearsal has no Vercel in front).

export const PROXY_HEADER = "x-cta-proxy-secret";
export const REAL_IP_HEADER = "x-real-ip";
// A header of our own: Vercel may replace x-real-ip on the hop to the API, but not a custom header.
export const VISITOR_HEADER = "x-cta-visitor";

/** The visitor's address as the host reports it: the first x-forwarded-for entry, else x-real-ip. */
export function visitorAddress(incoming: Headers): string | null {
  const first = incoming.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (first) return first;
  return incoming.get(REAL_IP_HEADER)?.trim() || null;
}

/** The request headers for the API: the visitor's own copy, minus anything that would forge the
 * two trusted headers, plus the shared secret (when one is configured) and the visitor address. */
export function forwardHeaders(incoming: Headers, secret: string | undefined): Headers {
  const out = new Headers(incoming);
  const address = visitorAddress(incoming);
  out.delete(PROXY_HEADER);
  out.delete(REAL_IP_HEADER);
  out.delete(VISITOR_HEADER); // always overwritten, never appended to or passed on from the client
  if (secret) {
    out.set(PROXY_HEADER, secret);
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
