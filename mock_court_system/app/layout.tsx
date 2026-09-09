import type React from "react"
import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { Analytics } from "@vercel/analytics/react"
import { ThemeProvider } from "@/components/theme-provider"
import "./globals.css"

export const metadata: Metadata = {
  title: "LexGentium｜国际商事仲裁听证仿真",
  description:
    "LexGentium 国际商事仲裁听证仿真：开庭、观庭、复盘。支持申请准备、答辩准备与仲裁听证。",
  keywords: [
    "LexGentium",
    "国际商事仲裁",
    "听证仿真",
    "申请准备",
    "答辩准备",
    "仲裁听证",
    "法律科技",
  ],
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
    <html lang="zh-CN" className={GeistSans.variable} data-scheme="ink" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[100] focus:rounded-md focus:border focus:border-border focus:bg-card focus:px-3 focus:py-2 focus:text-[13px] focus:shadow-sm"
        >
          跳到正文
        </a>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          {children}
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
