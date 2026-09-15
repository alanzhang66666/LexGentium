"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import { clientAuthHeaders } from "@/lib/session/unlock"
import { SCENARIO_LABELS } from "@/lib/labels"
import {
  History,
  Search,
  FileJson,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Filter,
} from "lucide-react"

interface APIHistoryStats {
  exists: boolean
  total_interactions: number
  by_scenario: Record<string, number>
  file_path?: string
}

interface APIInteraction {
  scenario: string
  case_id: string
  dialog_history: any[]
  response: any
  dialog_summary?: string
  last_message?: string
  turn_count?: number
}

export default function APIHistoryPage() {
  const [stats, setStats] = useState<APIHistoryStats | null>(null)
  const [interactions, setInteractions] = useState<APIInteraction[]>([])
  const [loading, setLoading] = useState(true)
  const [filterScenario, setFilterScenario] = useState<string>("all")
  const [filterCaseId, setFilterCaseId] = useState("")
  const [limit, setLimit] = useState(50)

  useEffect(() => {
    loadStats()
    loadInteractions()
  }, [filterScenario, filterCaseId, limit])

  const loadStats = async () => {
    try {
      const response = await fetch("/api/api-history/stats", { headers: { ...clientAuthHeaders() } })
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (err) {
      console.error("加载统计信息失败:", err)
    }
  }

  const loadInteractions = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterScenario !== "all") {
        params.append("scenario", filterScenario)
      }
      if (filterCaseId) {
        params.append("case_id", filterCaseId)
      }
      params.append("limit", limit.toString())
      params.append("offset", "0")

      const response = await fetch(`/api/api-history/list?${params.toString()}`, {
        headers: { ...clientAuthHeaders() },
      })
      if (response.ok) {
        const data = await response.json()
        setInteractions(data.interactions || [])
      }
    } catch (err) {
      console.error("加载交互历史失败:", err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">API 历史</h1>
          <p className="mt-1 text-sm text-muted-foreground">调用记录，用于调试。</p>
        </div>
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10 border border-primary/20">
                  <History className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <CardTitle>历史统计</CardTitle>
                  <CardDescription>API交互记录统计信息</CardDescription>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => { loadStats(); loadInteractions(); }}>
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {stats ? (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">历史文件状态</span>
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
                    <span className="text-sm text-muted-foreground">总交互数</span>
                    <span className="text-2xl font-bold">{stats.total_interactions}</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-semibold mb-2">按场景分布</div>
                  {Object.entries(stats.by_scenario || {}).map(([scenario, count]) => (
                    <div key={scenario} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {SCENARIO_LABELS[scenario] || scenario}:
                      </span>
                      <span className="font-semibold">{count as number}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-8">
                <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* 筛选和搜索 */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <Filter className="w-5 h-5" />
              筛选条件
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>场景</Label>
                <Select value={filterScenario} onValueChange={setFilterScenario}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部场景</SelectItem>
                    <SelectItem value="CD">{SCENARIO_LABELS.CD}</SelectItem>
                    <SelectItem value="DD">{SCENARIO_LABELS.DD}</SelectItem>
                    <SelectItem value="CI">{SCENARIO_LABELS.CI}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>案例ID</Label>
                <Input
                  value={filterCaseId}
                  onChange={(e) => setFilterCaseId(e.target.value)}
                  placeholder="输入案例ID..."
                />
              </div>
              <div className="space-y-2">
                <Label>显示数量</Label>
                <Select value={limit.toString()} onValueChange={(v) => setLimit(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="20">20条</SelectItem>
                    <SelectItem value="50">50条</SelectItem>
                    <SelectItem value="100">100条</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 交互列表 */}
        <Card>
          <CardHeader>
            <CardTitle>交互记录</CardTitle>
            <CardDescription>共 {interactions.length} 条记录</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : interactions.length > 0 ? (
              <div className="space-y-4">
                {interactions.map((interaction, index) => (
                  <Card key={index} className="border">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-base">
                            {SCENARIO_LABELS[interaction.scenario] || interaction.scenario} · {interaction.case_id}
                          </CardTitle>
                          <CardDescription className="mt-1">
                            轮次: {interaction.turn_count || interaction.dialog_history?.length || 0}
                          </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs px-2 py-1 bg-primary/10 rounded">
                            {interaction.scenario}
                          </span>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {interaction.dialog_summary && (
                        <div>
                          <div className="text-xs font-semibold text-muted-foreground mb-1">对话摘要</div>
                          <p className="text-sm">{interaction.dialog_summary}</p>
                        </div>
                      )}
                      {interaction.last_message && (
                        <div>
                          <div className="text-xs font-semibold text-muted-foreground mb-1">最后消息</div>
                          <p className="text-sm">{interaction.last_message}</p>
                        </div>
                      )}
                      <details className="text-sm">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                          查看完整数据
                        </summary>
                        <pre className="mt-2 bg-muted p-3 rounded text-xs overflow-x-auto">
                          {JSON.stringify(interaction, null, 2)}
                        </pre>
                      </details>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <FileJson className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>暂无交互记录</p>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </WorkbenchShell>
  )
}

