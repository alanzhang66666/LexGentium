"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { SchemePicker } from "@/components/scheme-picker"
import { ThemeToggle } from "@/components/theme-toggle"
import { CommandPalette } from "@/components/command-palette"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { getConversation } from "@/lib/api/conversation"
import { STAGE_LABELS } from "@/lib/labels"
import {
  NAV_ACTIONS,
  NAV_GROUPS,
  activeNavGroup,
  isNavActionDisabled,
  resolveNavHref,
  type NavGroupId,
} from "@/lib/nav-actions"
import { readLastSessionId, subscribeLastSession } from "@/lib/session/last-session"
import { clearUnlock, isUnlocked, subscribeUnlock } from "@/lib/session/unlock"
import type { ConversationInfo } from "@/lib/conversation-types"
import { BrandLockup, BrandMark } from "@/components/brand"
import { cn } from "@/lib/utils"

function actionsFor(group: NavGroupId) {
  return NAV_ACTIONS.filter((action) => action.group === group)
}

function useUnlocked() {
  const [unlocked, setUnlocked] = useState(false)
  useEffect(() => {
    setUnlocked(isUnlocked())
    return subscribeUnlock(setUnlocked)
  }, [])
  return unlocked
}

function AuthCtas({
  unlocked,
  size = "lg",
}: {
  unlocked: boolean
  size?: "sm" | "default" | "lg"
}) {
  if (unlocked) {
    return (
      <>
        <span className="px-2 py-1.5 text-[13px] text-muted-foreground">已开通</span>
        <Button type="button" variant="outline" size={size} onClick={() => clearUnlock()}>
          退出
        </Button>
      </>
    )
  }

  return (
    <>
      <Button asChild variant="outline" size={size}>
        <Link href="/login">登录</Link>
      </Button>
      <Button asChild size={size}>
        <Link href="/register">开通</Link>
      </Button>
    </>
  )
}

function NavActionRows({
  group,
  sessionId,
  onNavigate,
}: {
  group: NavGroupId
  sessionId: string | null
  onNavigate?: () => void
}) {
  const router = useRouter()
  return (
    <>
      {actionsFor(group).map((action) => {
        const disabled = isNavActionDisabled(action, sessionId)
        return (
          <DropdownMenuItem
            key={action.id}
            disabled={disabled}
            onSelect={() => {
              if (disabled) return
              router.push(resolveNavHref(action, sessionId))
              onNavigate?.()
            }}
          >
            <span className="flex min-w-0 flex-col">
              <span className="font-medium">{action.title}</span>
              <span className="text-[12px] font-normal text-muted-foreground">{action.description}</span>
            </span>
          </DropdownMenuItem>
        )
      })}
    </>
  )
}

function GroupTrigger({
  group,
  active,
}: {
  group: { id: NavGroupId; label: string }
  active: boolean
}) {
  return (
    <DropdownMenuTrigger
      className={cn(
        "rounded-md px-2 py-1.5 text-[13px] font-medium outline-none",
        "focus-visible:ring-1 focus-visible:ring-ring",
        active ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground",
      )}
    >
      {group.label}
    </DropdownMenuTrigger>
  )
}

function HealthDot({ ok, pending }: { ok: boolean | null; pending: boolean }) {
  const tone = pending ? "bg-muted-foreground/50" : ok ? "bg-success" : "bg-destructive"
  const label = pending ? "正在检查后端" : ok ? "后端可用" : "后端未连接"
  return (
    <span className="inline-flex size-8 items-center justify-center" title={label} aria-label={label}>
      <span className={cn("size-2 rounded-full", tone)} />
    </span>
  )
}

function SessionChip({
  sessionId,
  info,
  healthOk,
}: {
  sessionId: string | null
  info: ConversationInfo | null
  healthOk: boolean | null
}) {
  const router = useRouter()

  let label = "未开场"
  if (healthOk === false) {
    label = "未连接"
  } else if (sessionId) {
    const shortId = sessionId.slice(0, 8)
    const stage = info?.current_stage ? STAGE_LABELS[info.current_stage] || info.current_stage : null
    const flags: string[] = []
    if (info) {
      if (info.links?.game_id) flags.push("策略已开")
      if (!info.links?.report_id) flags.push("未对照")
    }
    label = [shortId, stage, ...flags].filter(Boolean).join(" · ")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "max-w-[220px] truncate rounded-full border border-border px-2.5 py-1 text-left text-[12px] font-medium",
          "font-mono tabular-nums outline-none hover:bg-secondary focus-visible:ring-1 focus-visible:ring-ring",
        )}
        title={label}
      >
        {label}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>本场</DropdownMenuLabel>
        {!sessionId || healthOk === false ? (
          <DropdownMenuItem disabled>
            <span className="text-muted-foreground">{healthOk === false ? "后端未连接" : "还没有本场会话"}</span>
          </DropdownMenuItem>
        ) : (
          <>
            <DropdownMenuItem onSelect={() => router.push(`/conversation/${sessionId}`)}>
              <span className="flex flex-col">
                <span className="font-medium">本场听证</span>
                <span className="text-[12px] font-normal text-muted-foreground">打开文字记录</span>
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => router.push(`/hearing-3d?sessionId=${encodeURIComponent(sessionId)}`)}
            >
              <span className="flex flex-col">
                <span className="font-medium">观庭</span>
                <span className="text-[12px] font-normal text-muted-foreground">进入本场三维听证</span>
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => router.push(`/evaluation?session=${encodeURIComponent(sessionId)}&pane=contrast`)}
            >
              <span className="flex flex-col">
                <span className="font-medium">对照本场</span>
                <span className="text-[12px] font-normal text-muted-foreground">用本场记录做对照</span>
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => router.push(`/evaluation?session=${encodeURIComponent(sessionId)}&pane=strategy`)}
            >
              <span className="flex flex-col">
                <span className="font-medium">策略推演</span>
                <span className="text-[12px] font-normal text-muted-foreground">立场与反事实</span>
              </span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MarketingBar() {
  const pathname = usePathname() || "/"
  const unlocked = useUnlocked()
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1120px] items-center justify-between gap-3 px-4">
        <Link href="/" className="flex min-w-0 items-center gap-2.5 hover:opacity-80">
          <BrandLockup />
          <span className="hidden truncate text-[13px] font-normal text-muted-foreground sm:inline">研究平台</span>
        </Link>
        <div className="flex shrink-0 items-center gap-1">
          <Link
            href="/docs"
            className={cn(
              "rounded-md px-2 py-1.5 text-[13px] font-medium",
              pathname.startsWith("/docs")
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground",
            )}
          >
            文档
          </Link>
          <Link
            href="/about"
            className={cn(
              "rounded-md px-2 py-1.5 text-[13px] font-medium",
              pathname.startsWith("/about")
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground",
            )}
          >
            关于
          </Link>
          <Button asChild variant={unlocked ? "default" : "outline"} size="lg">
            <Link href="/conversation">开庭</Link>
          </Button>
          <AuthCtas unlocked={unlocked} size="lg" />
          <SchemePicker />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

function WorkbenchBar() {
  const pathname = usePathname() || "/"
  const currentGroup = activeNavGroup(pathname)
  const unlocked = useUnlocked()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [info, setInfo] = useState<ConversationInfo | null>(null)
  const [healthOk, setHealthOk] = useState<boolean | null>(null)
  const [healthPending, setHealthPending] = useState(true)

  useEffect(() => {
    setSessionId(readLastSessionId())
    return subscribeLastSession(setSessionId)
  }, [])

  useEffect(() => {
    let cancelled = false
    const ping = async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" })
        if (!cancelled) {
          setHealthOk(res.ok)
          setHealthPending(false)
        }
      } catch {
        if (!cancelled) {
          setHealthOk(false)
          setHealthPending(false)
        }
      }
    }
    void ping()
    const timer = window.setInterval(ping, 20000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!sessionId || healthOk === false) {
      setInfo(null)
      return
    }
    let cancelled = false
    getConversation(sessionId)
      .then((data) => {
        if (!cancelled) setInfo(data)
      })
      .catch(() => {
        if (!cancelled) setInfo(null)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, healthOk])

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-12 max-w-none items-center justify-between gap-3 px-4">
        <Link href="/" className="flex shrink-0 items-center hover:opacity-80">
          <BrandMark />
        </Link>

        <nav className="hidden items-center gap-0.5 sm:flex">
          {NAV_GROUPS.map((group) => (
            <DropdownMenu key={group.id}>
              <GroupTrigger group={group} active={currentGroup === group.id} />
              <DropdownMenuContent align="start">
                <NavActionRows group={group.id} sessionId={healthOk === false ? null : sessionId} />
              </DropdownMenuContent>
            </DropdownMenu>
          ))}
        </nav>

        <div className="flex items-center gap-1.5">
          <div className="sm:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(
                  "rounded-md px-2 py-1.5 text-[13px] font-medium outline-none",
                  "text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring",
                )}
              >
                菜单
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-[70vh] overflow-y-auto">
                {NAV_GROUPS.map((group, index) => (
                  <div key={group.id}>
                    {index > 0 ? <DropdownMenuSeparator /> : null}
                    <DropdownMenuLabel>{group.label}</DropdownMenuLabel>
                    <NavActionRows group={group.id} sessionId={healthOk === false ? null : sessionId} />
                  </div>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <SessionChip sessionId={healthOk === false ? null : sessionId} info={info} healthOk={healthOk} />
          <HealthDot ok={healthOk} pending={healthPending} />
          <AuthCtas unlocked={unlocked} size="default" />
          <SchemePicker />
          <ThemeToggle />
        </div>
      </div>
      <CommandPalette sessionId={healthOk === false ? null : sessionId} />
    </header>
  )
}

export function Navigation({ compact = false }: { compact?: boolean }) {
  return compact ? <WorkbenchBar /> : <MarketingBar />
}
