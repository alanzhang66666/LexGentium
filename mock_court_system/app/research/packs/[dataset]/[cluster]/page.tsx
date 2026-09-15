"use client"

import { Suspense } from "react"
import { useParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { WorkbenchShell } from "@/components/shell"
import { PackWorkbench } from "@/components/research/pack-workbench"

function ResearchPackInner() {
  const params = useParams()
  const dataset = String(params.dataset || "")
  const cluster = String(params.cluster || "")
  return <PackWorkbench dataset={dataset} cluster={cluster} />
}

export default function ResearchPackPage() {
  return (
    <WorkbenchShell footer={false}>
      <Suspense
        fallback={
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            正在打开标注页
          </div>
        }
      >
        <ResearchPackInner />
      </Suspense>
    </WorkbenchShell>
  )
}
