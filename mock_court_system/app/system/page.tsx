"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Activity, ExternalLink, RefreshCw, Server } from "lucide-react"
import { PUBLIC_BACKEND_URL } from "@/lib/public-backend-url"

interface HealthPayload {
  status?: string
  time?: string
  paths?: Record<string, unknown>
  error?: string
  detail?: string
  suggestion?: string
}

const MAPPINGS: {
  backend: string
  desc: string
  frontendPage: { href: string; label: string }
  nextApi: string
}[] = [
  {
    backend: "GET /health",
    desc: "健康检查与关键路径探测",
    frontendPage: { href: "/system", label: "系统状态（本页）" },
    nextApi: "GET /api/health",
  },
  {
    backend: "POST /",
    desc: "无状态单轮模拟（不写入会话库）",
    frontendPage: { href: "/simulate", label: "模拟器" },
    nextApi: "POST /api/simulate",
  },
  {
    backend: "POST /conversation/start",
    desc: "创建会话",
    frontendPage: { href: "/conversation", label: "对话" },
    nextApi: "POST /api/conversation/start",
  },
  {
    backend: "POST /conversation/import",
    desc: "导入历史为会话",
    frontendPage: { href: "/simulate", label: "模拟器（导入）" },
    nextApi: "POST /api/conversation/import",
  },
  {
    backend: "GET /conversation/list",
    desc: "会话列表（分页）",
    frontendPage: { href: "/conversation", label: "对话" },
    nextApi: "GET /api/conversation/list",
  },
  {
    backend: "GET /conversation/{session_id}",
    desc: "会话详情",
    frontendPage: { href: "/conversation", label: "对话 → 进入会话" },
    nextApi: "GET /api/conversation/[sessionId]",
  },
  {
    backend: "POST /conversation/{session_id}/message",
    desc: "会话内发消息",
    frontendPage: { href: "/conversation", label: "对话 → 会话页" },
    nextApi: "POST /api/conversation/[sessionId]/message",
  },
  {
    backend: "DELETE /conversation/{session_id}",
    desc: "删除会话",
    frontendPage: { href: "/conversation", label: "对话 / 会话页" },
    nextApi: "DELETE /api/conversation/[sessionId]",
  },
  {
    backend: "POST /evaluate",
    desc: "启动评测任务",
    frontendPage: { href: "/evaluation", label: "评测" },
    nextApi: "POST /api/evaluate",
  },
  {
    backend: "GET /evaluation/results",
    desc: "评测报告列表",
    frontendPage: { href: "/evaluation", label: "评测" },
    nextApi: "GET /api/evaluate",
  },
  {
    backend: "GET /evaluation/status/{report_id}",
    desc: "评测任务状态",
    frontendPage: { href: "/evaluation", label: "评测（轮询）" },
    nextApi: "GET /api/evaluate?report_id=…",
  },
  {
    backend: "GET /evaluation/reports/{report_id}",
    desc: "评测报告详情",
    frontendPage: { href: "/evaluation", label: "评测 → 报告详情" },
    nextApi: "GET /api/evaluate/reports/[reportId]",
  },
  {
    backend: "POST /database/search",
    desc: "法条检索",
    frontendPage: { href: "/database", label: "数据库" },
    nextApi: "POST /api/database/search",
  },
  {
    backend: "GET /database/stats",
    desc: "法条库统计",
    frontendPage: { href: "/database", label: "数据库" },
    nextApi: "GET /api/database/stats",
  },
  {
    backend: "GET /api-history/stats",
    desc: "API 调用统计",
    frontendPage: { href: "/api-history", label: "API 历史" },
    nextApi: "GET /api/api-history/stats",
  },
  {
    backend: "GET /api-history/list",
    desc: "API 调用列表（筛选/分页）",
    frontendPage: { href: "/api-history", label: "API 历史" },
    nextApi: "GET /api/api-history/list",
  },
]

export default function SystemPage() {
  const [health, setHealth] = useState<HealthPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch("/api/health", { cache: "no-store" })
      const data = (await res.json()) as HealthPayload
      if (!res.ok) {
        setHealth(data)
        setError(data.detail || data.error || `HTTP ${res.status}`)
        return
      }
      setHealth(data)
    } catch (e) {
      setHealth(null)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadHealth()
  }, [loadHealth])

  const swaggerHref = `${PUBLIC_BACKEND_URL.replace(/\/$/, "")}/docs`

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <ScrollIndicator />

      <section className="border-b bg-muted/30">
        <div className="container mx-auto px-4 md:px-8 py-8 md:py-12">
          <div className="max-w-4xl space-y-3">
            <h1 className="text-3xl md:text-4xl font-bold text-balance flex items-center gap-3">
              <Server className="w-8 h-8 text-primary" />
              系统状态与接口映射
            </h1>
            <p className="text-muted-foreground leading-relaxed">
              展示后端健康检查结果，并列出 FastAPI 能力与前端页面、Next 代理路由的一一对应关系（本机默认后端{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs">{PUBLIC_BACKEND_URL}</code>
              ）。
            </p>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => loadHealth()} disabled={loading}>
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                刷新健康检查
              </Button>
              <Button variant="outline" size="sm" asChild>
                <a href={swaggerHref} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="w-4 h-4 mr-2" />
                  打开后端 Swagger（/docs）
                </a>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/docs">文档中心</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12 space-y-8">
        <Card className="border-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5" />
              后端健康检查（GET /api/health → GET /health）
            </CardTitle>
            <CardDescription>由 Next 服务端转发；失败时多为后端未启动或地址配置错误。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {error && (
              <Alert variant="destructive">
                <AlertDescription className="font-mono text-sm whitespace-pre-wrap">{error}</AlertDescription>
              </Alert>
            )}
            {loading && !health && <p className="text-sm text-muted-foreground">加载中…</p>}
            {health && (
              <pre className="bg-muted p-4 rounded-lg text-xs font-mono overflow-x-auto max-h-80">
                {JSON.stringify(health, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <h2 className="text-2xl font-bold">后端能力 → 前端入口</h2>
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b text-left">
                  <th className="p-3 font-semibold whitespace-nowrap">FastAPI</th>
                  <th className="p-3 font-semibold">说明</th>
                  <th className="p-3 font-semibold whitespace-nowrap">前端页面</th>
                  <th className="p-3 font-semibold whitespace-nowrap">Next 代理</th>
                </tr>
              </thead>
              <tbody>
                {MAPPINGS.map((row) => (
                  <tr key={row.backend + row.nextApi} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="p-3 font-mono text-xs align-top">{row.backend}</td>
                    <td className="p-3 text-muted-foreground align-top">{row.desc}</td>
                    <td className="p-3 align-top">
                      <Link href={row.frontendPage.href} className="text-primary hover:underline">
                        {row.frontendPage.label}
                      </Link>
                    </td>
                    <td className="p-3 font-mono text-xs align-top">{row.nextApi}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
