import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Pin the workspace root to this app so Turbopack doesn't try to infer it
  // from an unrelated lockfile higher up the filesystem (e.g. in $HOME).
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
