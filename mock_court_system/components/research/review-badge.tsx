import type { ReviewState } from "@/lib/research"
import { cn } from "@/lib/utils"
import { REVIEW_STATE_LABELS } from "@/components/research/labels"

const TONE: Record<ReviewState, string> = {
  pending: "border-border bg-secondary text-muted-foreground",
  tech_checked: "border-primary/30 bg-primary/10 text-primary",
  law_reviewed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  disputed: "border-destructive/30 bg-destructive/10 text-destructive",
}

export function ReviewBadge({
  state,
  className,
}: {
  state?: ReviewState | string | null
  className?: string
}) {
  const review = (state || "pending") as ReviewState
  const label = REVIEW_STATE_LABELS[review] || review
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        TONE[review] || TONE.pending,
        className,
      )}
    >
      {label}
    </span>
  )
}
