"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Command } from "cmdk"
import {
  NAV_ACTIONS,
  NAV_GROUPS,
  isNavActionDisabled,
  resolveNavHref,
  type NavGroupId,
} from "@/lib/nav-actions"

export function CommandPalette({ sessionId }: { sessionId: string | null }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setOpen((value) => !value)
      }
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[80]">
      <button
        type="button"
        className="absolute inset-0 bg-black/72"
        aria-label="关闭命令条"
        onClick={() => setOpen(false)}
      />
      <div className="relative mx-auto mt-[12vh] w-full max-w-lg px-4">
        <Command
          label="命令条"
          className="overflow-hidden rounded-md border border-border bg-card text-card-foreground shadow-none"
        >
          <Command.Input
            autoFocus
            placeholder="跳转到开庭、观庭、复盘、系统…"
            className="h-10 w-full border-b border-border bg-transparent px-3 text-[13px] outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="max-h-80 overflow-y-auto p-1">
            <Command.Empty className="px-3 py-6 text-center text-[13px] text-muted-foreground">
              没有匹配的入口
            </Command.Empty>
            {NAV_GROUPS.map((group) => (
              <Command.Group
                key={group.id}
                heading={group.label}
                className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[12px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground"
              >
                {NAV_ACTIONS.filter((action) => action.group === group.id).map((action) => {
                  const disabled = isNavActionDisabled(action, sessionId)
                  return (
                    <Command.Item
                      key={action.id}
                      value={`${action.title} ${action.description} ${group.label}`}
                      disabled={disabled}
                      className="flex cursor-pointer flex-col rounded-md px-2 py-1.5 text-[13px] data-[disabled=true]:opacity-50 data-[selected=true]:bg-secondary"
                      onSelect={() => {
                        if (disabled) return
                        router.push(resolveNavHref(action, sessionId))
                        setOpen(false)
                      }}
                    >
                      <span className="font-medium">{action.title}</span>
                      <span className="text-[12px] text-muted-foreground">{action.description}</span>
                    </Command.Item>
                  )
                })}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
        <p className="mt-2 text-center text-[12px] text-muted-foreground">Esc 关闭 · 与顶栏四组同一份入口</p>
      </div>
    </div>
  )
}

export function groupLabel(id: NavGroupId) {
  return NAV_GROUPS.find((group) => group.id === id)?.label ?? id
}
