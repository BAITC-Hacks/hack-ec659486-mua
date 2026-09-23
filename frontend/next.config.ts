import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone: минимальный бандл с собственным server.js для Docker (см. Dockerfile).
  output: "standalone",
  // Единый origin для браузера: /api/* и /health проксируются в backend (ссылки на скачивание работают без CORS).
  async rewrites() {
    const api = process.env.API_URL_INTERNAL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }, { source: "/health", destination: `${api}/health` }];
  },
  reactStrictMode: true,
};

export default nextConfig;
