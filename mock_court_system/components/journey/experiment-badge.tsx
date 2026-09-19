import { EXPERIMENTAL_LABEL, isExperimentalApi, isExperimentalPage } from "@/lib/route-catalog"
import { cn } from "@/lib/utils"

export function ExperimentBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400",
        className,
      )}
    >
      {EXPERIMENTAL_LABEL}
    </span>
  )
}

export function PageExperimentBadge({ path, className }: { path: string; className?: string }) {
  return isExperimentalPage(path) ? <ExperimentBadge className={className} /> : null
}

export function ApiExperimentBadge({ path, className }: { path: string; className?: string }) {
  return isExperimentalApi(path) ? <ExperimentBadge className={className} /> : null
}
