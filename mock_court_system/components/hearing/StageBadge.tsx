"use client"

import { STAGE_LABELS, SUB_STAGE_LABELS, roleDisplayName } from "@/lib/labels"
import type { CourtStage, CourtSubStage } from "@/lib/conversation-types"

export function StageBadge({
  stage,
  subStage,
  nextSpeaker,
  scenario,
}: {
  stage?: CourtStage | string | null
  subStage?: CourtSubStage | string | null
  nextSpeaker?: string | null
  scenario?: string
}) {
  if (!stage && !subStage && !nextSpeaker) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {stage ? (
        <span className="rounded-md border border-border bg-secondary px-2 py-0.5 text-[12px] font-medium">
          {STAGE_LABELS[stage] || stage}
        </span>
      ) : null}
      {subStage && scenario === "CI" ? (
        <span className="rounded-md border border-border px-2 py-0.5 text-[12px] text-muted-foreground">
          {SUB_STAGE_LABELS[subStage] || subStage}
        </span>
      ) : null}
      {nextSpeaker ? (
        <span className="text-[12px] text-muted-foreground">
          下一发言 {roleDisplayName(nextSpeaker)}
        </span>
      ) : null}
    </div>
  )
}
