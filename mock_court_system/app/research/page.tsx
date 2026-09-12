"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertCircle, Loader2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { WorkbenchShell } from "@/components/shell"
import { ReviewBadge } from "@/components/research/review-badge"
import { DATASET_LABELS, TASK_TYPE_LABELS } from "@/components/research/labels"
import { describeApiError } from "@/lib/api/config"
import { listResearchPacks } from "@/lib/api/simulation"
import type { DatasetId, PackSummary } from "@/lib/research"

type ListedPack = PackSummary & { overlay_count?: number }

export default function ResearchPackListPage() {
  const [packs, setPacks] = useState<ListedPack[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listResearchPacks()
      .then((payload) => {
        if (!cancelled) setPacks((payload.packs || []) as unknown as ListedPack[])
      })
      .catch((err) => {
        if (!cancelled) setError(describeApiError(err, "无法加载研究包列表"))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">研究</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            材料标注工作台：对照原文、提取片段与字段，并从字段跳回 source_id。覆盖层写入独立库，不改 pack.json。
          </p>
        </div>
        {error ? (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            正在列出研究包
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {packs.map((pack) => {
              const dataset = pack.dataset_id as DatasetId
              const href = `/research/packs/${encodeURIComponent(pack.dataset_id)}/${encodeURIComponent(pack.cluster_id)}`
              return (
                <Link key={`${pack.dataset_id}/${pack.cluster_id}`} href={href}>
                  <Card className="h-full transition-colors hover:bg-secondary/40">
                    <CardHeader>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <CardTitle className="text-[16px]">{pack.case_name || pack.cluster_id}</CardTitle>
                          <CardDescription className="mt-1 font-mono text-[12px]">
                            {DATASET_LABELS[dataset] || pack.dataset_id} / {pack.cluster_id}
                          </CardDescription>
                        </div>
                        <ReviewBadge state={pack.review_state} />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-1 text-[13px] text-muted-foreground">
                      <p>
                        {TASK_TYPE_LABELS[pack.task_type] || pack.task_type} · 版本 {pack.pack_version}
                      </p>
                      <p>
                        文书 {pack.document_ids?.length ?? 0} 份
                        {typeof pack.overlay_count === "number" ? ` · 覆盖层 ${pack.overlay_count}` : ""}
                      </p>
                    </CardContent>
                  </Card>
                </Link>
              )
            })}
          </div>
        )}
        {!loading && !error && packs.length === 0 ? (
          <p className="text-sm text-muted-foreground">还没有研究包。请先放入 data/research_packs。</p>
        ) : null}
      </main>
    </WorkbenchShell>
  )
}
