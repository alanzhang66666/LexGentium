import type React from "react"
import type { Metadata } from "next"
import { Analytics } from "@vercel/analytics/react"
import "./globals.css"

export const metadata: Metadata = {
  title: "LexGentium | 基于扩展式博弈建模的多智能体协同模拟法庭系统",
  description: "LexGentium——基于扩展式博弈建模的多智能体协同模拟法庭系统，支持起诉状生成(CD)、答辩状生成(DD)和法庭判决(CI)场景的智能化模拟与分析",
  keywords: ["LexGentium", "扩展式博弈", "多智能体系统", "模拟法庭", "法律科技", "AI法庭", "Legal Tech", "Court Simulation", "Game Theory"],
  generator: "v0.app",
  icons: {
    icon: [
      {
        url: "/icon-light-32x32.png",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/icon-dark-32x32.png",
        media: "(prefers-color-scheme: dark)",
      },
      {
        url: "/icon.svg",
        type: "image/svg+xml",
      },
    ],
    apple: "/apple-icon.png",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN">
      <body className="font-sans antialiased">
        {children}
        <Analytics />
      </body>
    </html>
  )
}
