// The page calls /api/* on its own origin; Next forwards it to the local API. The browser never
// talks to the API host, so there is no CORS, and the API can stay bound to 127.0.0.1.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Hide the dev-only "N" route indicator (supported option in Next 16: devIndicators: false).
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
