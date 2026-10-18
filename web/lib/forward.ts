// What the page's proxy (proxy.ts) sends to the API. Plain functions, so they can be tested.
// The API trusts the visitor address in x-real-ip only when x-cta-proxy-secret matches its own
// CTA_PROXY_SECRET (src/cta/api/guard.py). Vercel sets x-forwarded-for / x-real-ip itself and
// overwrites any value a visitor sends (https://vercel.com/docs/headers/request-headers).

export const PROXY_HEADER = "x-cta-proxy-secret";
export const REAL_IP_HEADER = "x-real-ip";

/** The visitor's address as the host reports it: x-real-ip, else the first x-forwarded-for entry. */
export function visitorAddress(incoming: Headers): string | null {
  const real = incoming.get(REAL_IP_HEADER)?.trim();
  if (real) return real;
  const first = incoming.get("x-forwarded-for")?.split(",")[0]?.trim();
  return first || null;
}

/** The request headers for the API: the visitor's own copy, minus anything that would forge the
 * two trusted headers, plus the shared secret (when one is configured) and the visitor address. */
export function forwardHeaders(incoming: Headers, secret: string | undefined): Headers {
  const out = new Headers(incoming);
  const address = visitorAddress(incoming);
  out.delete(PROXY_HEADER);
  out.delete(REAL_IP_HEADER);
  if (secret) {
    out.set(PROXY_HEADER, secret);
    if (address) out.set(REAL_IP_HEADER, address);
  }
  return out;
}

/** Where /api/ask and /api/feedback go: the API origin with the /api prefix removed. */
export function apiTarget(pathname: string, search: string, apiUrl: string | undefined): URL {
  return new URL(pathname.replace(/^\/api/, "") + search, apiUrl || "http://127.0.0.1:8000");
}
