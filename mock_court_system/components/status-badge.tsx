import type React from "react"
import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: "ready" | "loading" | "error" | "success"
  children: React.ReactNode
}

export function StatusBadge({ status, children }: StatusBadgeProps) {
  const statusClasses = {
    ready: "bg-secondary text-secondary-foreground",
    loading: "bg-primary/10 text-primary border-primary/20",
    error: "bg-destructive/10 text-destructive border-destructive/20",
    success: "bg-accent/10 text-accent border-accent/20",
  }

  const indicatorClasses = {
    ready: "bg-secondary-foreground/40",
    loading: "bg-primary animate-pulse",
    error: "bg-destructive",
    success: "bg-accent",
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium border transition-colors",
        statusClasses[status],
      )}
    >
      <div className={cn("h-2 w-2 rounded-full transition-all", indicatorClasses[status])} />
      {children}
    </div>
  )
}
