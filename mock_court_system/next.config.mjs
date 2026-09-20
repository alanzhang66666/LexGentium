/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ["127.0.0.1"],
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei", "@pixiv/three-vrm"],
  async redirects() {
    return [
      { source: "/court3d", destination: "/hearing-3d", permanent: false },
      { source: "/court3d/replay", destination: "/hearing-3d", permanent: false },
      { source: "/court3d/:sessionId", destination: "/hearing-3d?sessionId=:sessionId", permanent: false },
    ]
  },
}

export default nextConfig
