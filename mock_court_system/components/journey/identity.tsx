import { cn } from "@/lib/utils"

export interface IdentityItem {
  label: string
  value?: string | null
}

export function IdentityChips({ items, className }: { items: IdentityItem[]; className?: string }) {
  const visible = items.filter((item) => typeof item.value === "string" && item.value.length > 0)
  if (visible.length === 0) return null
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", className)}>
      {visible.map((item) => (
        <span key={item.label} className="inline-flex items-baseline gap-1 text-[11px] text-muted-foreground">
          <span>{item.label}</span>
          <code className="font-mono text-[11px] text-foreground/80 break-all">{item.value}</code>
        </span>
      ))}
    </div>
  )
}
