"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { WorkbenchShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { CasePicker } from "@/components/hearing/CasePicker"
import { listConversations, startConversation } from "@/lib/api"
import { SCENARIO_LABELS } from "@/lib/labels"
import { writeLastSessionId } from "@/lib/session/last-session"
import type { ConversationSummary, Scenario } from "@/lib/conversation-types"

export default function Court3dLobbyPage() {
  const router = useRouter()
  const [sessions, setSessions] = useState<ConversationSummary[]>([])
  const [scenario, setScenario] = useState<Scenario>("CI")
  const [caseId, setCaseId] = useState("foreign_commercial_001")
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    listConversations(20)
      .then((data) => setSessions(data.sessions || []))
      .catch(() => setSessions([]))
  }, [])

  const create = async () => {
    setCreating(true)
    setError(null)
    try {
      const data = await startConversation({ scenario, case_id: caseId })
      writeLastSessionId(data.session_id)
      router.push(`/court3d/${data.session_id}?cast=foreign_commercial&mode=live`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败")
    } finally {
      setCreating(false)
    }
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">观庭</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            同一 session 的三维听证。外壳已接工作台；场景资产到位后替换画布。
          </p>
        </div>

        <div className="mx-auto max-w-3xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">进入听证室</CardTitle>
              <CardDescription>新建或打开已有会话 / 离线回放</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>场景</Label>
                  <Select value={scenario} onValueChange={(v) => setScenario(v as Scenario)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CI">{SCENARIO_LABELS.CI}</SelectItem>
                      <SelectItem value="CD">{SCENARIO_LABELS.CD}</SelectItem>
                      <SelectItem value="DD">{SCENARIO_LABELS.DD}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>案件</Label>
                  <CasePicker value={caseId} onChange={setCaseId} />
                </div>
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Button onClick={create} disabled={creating}>
                  {creating ? "创建中…" : "新建并进入"}
                </Button>
                <Button variant="outline" onClick={() => router.push("/court3d/replay")}>
                  离线回放
                </Button>
                <Button variant="ghost" asChild>
                  <Link href="/conversation">文字开庭</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="overflow-hidden rounded-lg border border-border">
            {sessions.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">暂无会话</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-[12px] text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">场景</th>
                    <th className="px-3 py-2 font-medium">案号</th>
                    <th className="px-3 py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id} className="border-b border-border/70 last:border-0 hover:bg-secondary">
                      <td className="px-3 py-2.5">{SCENARIO_LABELS[s.scenario] || s.scenario}</td>
                      <td className="px-3 py-2.5 font-medium">{s.case_id}</td>
                      <td className="px-3 py-2.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            writeLastSessionId(s.session_id)
                            router.push(`/court3d/${s.session_id}`)
                          }}
                        >
                          进入
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            writeLastSessionId(s.session_id)
                            router.push(`/conversation/${s.session_id}`)
                          }}
                        >
                          记录
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>
    </WorkbenchShell>
  )
}
