"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { WorkbenchShell } from "@/components/shell"
import { JourneyError } from "@/components/journey/states"
import { ReviewBadge } from "@/components/research/review-badge"
import { DATASET_LABELS, TASK_TYPE_LABELS } from "@/components/research/labels"
import { getResearchInventory, listResearchPacks, type ResearchInventory } from "@/lib/api/simulation"
import type { DatasetId, PackSummary } from "@/lib/research"

type ListedPack = PackSummary & { overlay_count?: number; classification?: string }

export default function ResearchPackListPage() {
  const [packs, setPacks] = useState<ListedPack[]>([])
  const [inventory, setInventory] = useState<ResearchInventory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [payload, inv] = await Promise.all([
        listResearchPacks(),
        getResearchInventory().catch(() => null),
      ])
      setPacks((payload.packs || []) as unknown as ListedPack[])
      setInventory(inv)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">研究</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            材料标注工作台：对照原文、提取片段与字段，并从字段跳回 source_id。覆盖层写入独立库，不改 pack.json。
          </p>
        </div>
        <JourneyError
          error={error}
          fallback="无法加载研究包列表"
          onRetry={() => void load()}
          busy={loading}
          className="mb-4"
        />
        {inventory ? (
          <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-[13px] text-muted-foreground">
            正式研究包 <span className="font-medium text-foreground">{inventory.formal_pack_count}</span>
            {inventory.formal_status === "no_formal_pack" ? "（no_formal_pack）" : ""}
            {" · "}技术夹具 {inventory.technical_fixtures.length} 个
            {" · "}未复核标注 {inventory.unreviewed_annotations?.count ?? 0} 份
            {" · "}案例 25：{inventory.case_25?.confirmation === "pending" ? "AI 辅助初标待确认" : inventory.case_25?.confirmation || "未知"}
            <p className="mt-1 text-[12px]">{inventory.disclaimer}</p>
          </div>
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
                        <div className="flex items-center gap-2">
                          {pack.classification === "technical_fixture" ? (
                            <span className="rounded border border-muted-foreground/30 px-1.5 py-0.5 text-[11px] text-muted-foreground">
                              技术夹具
                            </span>
                          ) : null}
                          <ReviewBadge state={pack.review_state} />
                        </div>
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
