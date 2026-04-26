import { AlertCircle, CheckCircle2, Info } from "lucide-react"
import { cn } from "@/lib/utils"

interface ValidationMessageProps {
  type: "error" | "success" | "info"
  message: string
  className?: string
}

export function ValidationMessage({ type, message, className }: ValidationMessageProps) {
  const icons = {
    error: AlertCircle,
    success: CheckCircle2,
    info: Info,
  }

  const styles = {
    error: "bg-destructive/10 text-destructive border-destructive/30",
    success: "bg-accent/10 text-accent border-accent/30",
    info: "bg-primary/10 text-primary border-primary/30",
  }

  const Icon = icons[type]

  return (
    <div
      className={cn(
        "flex items-start gap-2 px-3 py-2 rounded-lg border text-sm font-medium animate-in fade-in slide-in-from-top-1 duration-300",
        styles[type],
        className,
      )}
      role="alert"
    >
      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
      <span className="leading-relaxed">{message}</span>
    </div>
  )
}
