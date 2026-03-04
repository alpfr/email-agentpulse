import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for Docker deployment (minimal Node.js server)
  output: "standalone",
};

export default nextConfig;
