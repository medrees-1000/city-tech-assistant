// Next.js settings. The /api/ask and /api/feedback forwarding to the API is in proxy.ts (it has to
// add request headers, which a rewrite in this file cannot do). API_URL and CTA_PROXY_SECRET are
// read there at run time.

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Hide the dev-only "N" route indicator (supported option in Next 16: devIndicators: false).
  devIndicators: false,
};

export default nextConfig;
