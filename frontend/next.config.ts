import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // 서버사이드 프록시: Docker 내부에서는 INTERNAL_API_URL(service명), 외부에서는 NEXT_PUBLIC_API_URL
    const apiUrl =
      process.env.INTERNAL_API_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
