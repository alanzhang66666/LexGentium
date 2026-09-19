import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/http"
import { IdentityChips } from "./identity"

export function describeJourneyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return [err.message, err.detail, err.suggestion].filter(Boolean).join(" — ") || fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function JourneyError({
  error,
  fallback = "操作失败",
  onRetry,
  busy,
  className,
}: {
  error: unknown
  fallback?: string
  onRetry?: () => void
  busy?: boolean
  className?: string
}) {
  if (!error) return null
  const apiErr = error instanceof ApiError ? error : null
  const message = typeof error === "string" ? error : describeJourneyError(error, fallback)
  return (
    <Alert variant="destructive" className={className}>
      <AlertCircle className="size-4" />
      <AlertTitle className="flex items-center justify-between gap-3">
        <span>请求失败</span>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry} disabled={busy}>
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
            重试
          </Button>
        ) : null}
      </AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{message}</p>
        <IdentityChips
          items={[
            { label: "code", value: apiErr?.code },
            { label: "request_id", value: apiErr?.requestId },
            { label: "status", value: apiErr ? String(apiErr.status) : undefined },
          ]}
        />
      </AlertDescription>
    </Alert>
  )
}

export function JourneyEmpty({
  title,
  description,
  className,
}: {
  title: string
  description?: string
  className?: string
}) {
  return (
    <div className={className}>
      <p className="text-sm text-muted-foreground">{title}</p>
      {description ? <p className="mt-1 text-xs text-muted-foreground/80">{description}</p> : null}
    </div>
  )
}

export function JourneyTerminal({
  title,
  description,
  identity,
  ok = true,
  className,
}: {
  title: string
  description?: string
  identity?: { label: string; value?: string | null }[]
  ok?: boolean
  className?: string
}) {
  return (
    <Alert variant={ok ? "default" : "destructive"} className={className}>
      {ok ? <CheckCircle2 className="size-4" /> : <AlertCircle className="size-4" />}
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="space-y-2">
        {description ? <p>{description}</p> : null}
        {identity ? <IdentityChips items={identity} /> : null}
      </AlertDescription>
    </Alert>
  )
}
