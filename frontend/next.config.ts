import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone: минимальный бандл с собственным server.js для Docker (см. Dockerfile).
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
