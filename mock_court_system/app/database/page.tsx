"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import { clientAuthHeaders } from "@/lib/session/unlock"
import {
  Database,
  Search,
  FileText,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  BarChart3,
} from "lucide-react"

interface DatabaseStats {
  exists: boolean
  total_articles: number
  index_exists: boolean
  mapping_exists: boolean
  db_path?: string
  index_path?: string
}

interface LawSearchResult {
  law_id: string
  content: string
  score?: number
  law_name?: string
  article_number?: string
}

export default function DatabasePage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<LawSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [stats, setStats] = useState<DatabaseStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoadingStats(true)
    try {
      const response = await fetch("/api/database/stats", { headers: { ...clientAuthHeaders() } })
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (err) {
      console.error("加载统计信息失败:", err)
    } finally {
      setLoadingStats(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setError("请输入搜索关键词")
      return
    }

    setIsSearching(true)
    setError(null)
    setSearchResults([])

    try {
      const response = await fetch("/api/database/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...clientAuthHeaders(),
        },
        body: JSON.stringify({
          query: searchQuery,
          top_k: 10,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      setSearchResults(data.results || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "搜索失败")
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">数据库</h1>
          <p className="mt-1 text-sm text-muted-foreground">法条检索与索引状态。</p>
        </div>
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10 border border-primary/20">
                  <Database className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <CardTitle>数据库统计</CardTitle>
                  <CardDescription>法条数据库和索引状态</CardDescription>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={loadStats} disabled={loadingStats}>
                <RefreshCw className={`w-4 h-4 ${loadingStats ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loadingStats ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : stats ? (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">数据库状态</span>
                    {stats.exists ? (
                      <span className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="w-4 h-4" />
                        已加载
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-red-600">
                        <AlertCircle className="w-4 h-4" />
                        未找到
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">法条总数</span>
                    <span className="text-2xl font-bold">{stats.total_articles}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">FAISS索引</span>
                    {stats.index_exists ? (
                      <span className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="w-4 h-4" />
                        已加载
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-yellow-600">
                        <AlertCircle className="w-4 h-4" />
                        未找到
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">ID映射</span>
                    {stats.mapping_exists ? (
                      <span className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="w-4 h-4" />
                        已加载
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-yellow-600">
                        <AlertCircle className="w-4 h-4" />
                        未找到
                      </span>
                    )}
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  {stats.db_path && (
                    <div>
                      <span className="text-muted-foreground">数据库路径:</span>
                      <code className="ml-2 bg-muted px-2 py-1 rounded text-xs">{stats.db_path}</code>
                    </div>
                  )}
                  {stats.index_path && (
                    <div>
                      <span className="text-muted-foreground">索引路径:</span>
                      <code className="ml-2 bg-muted px-2 py-1 rounded text-xs">{stats.index_path}</code>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>无法加载数据库统计信息</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* 法条搜索 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 border border-primary/20">
                <Search className="w-5 h-5 text-primary" />
              </div>
              法条搜索
            </CardTitle>
            <CardDescription>使用向量检索和关键词匹配搜索相关法条</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="输入关键词搜索法条..."
                className="flex-1"
              />
              <Button onClick={handleSearch} disabled={isSearching || !stats?.exists}>
                {isSearching ? (
                  <>
                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin mr-2" />
                    搜索中...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    搜索
                  </>
                )}
              </Button>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {searchResults.length > 0 && (
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  找到 {searchResults.length} 条相关法条
                </div>
                {searchResults.map((result, index) => (
                  <Card key={index} className="border">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">
                          {result.law_name || "法条"} {result.article_number || ""}
                        </CardTitle>
                        {result.score !== undefined && (
                          <span className="text-xs text-muted-foreground">
                            相似度: {(result.score * 100).toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.content}</p>
                      {result.law_id && (
                        <div className="mt-2 text-xs text-muted-foreground">
                          ID: <code className="bg-muted px-1 py-0.5 rounded">{result.law_id}</code>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {searchResults.length === 0 && !isSearching && searchQuery && !error && (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>未找到相关法条</p>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </WorkbenchShell>
  )
}

