/** @type {import('next').NextConfig} */
const nextConfig = {
  serverExternalPackages: ["better-sqlite3"],
  turbopack: {},

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // Prevent clickjacking
          { key: "X-Frame-Options", value: "DENY" },
          // Prevent MIME sniffing
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Strict referrer policy — don't leak the URL to third parties
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Basic CSP: only serve content from self + CDNs already in use
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // Next.js requires unsafe-eval in dev
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob:",
              "connect-src 'self'",
              "frame-ancestors 'none'",
            ].join("; "),
          },
          // Disable browser features not needed by this internal tool
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },

  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        "better-sqlite3": false,
        fs: false,
        path: false,
        os: false,
      };
    }
    return config;
  },
};

module.exports = nextConfig;
