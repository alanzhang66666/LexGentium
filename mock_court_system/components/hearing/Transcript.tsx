"use client"

import { MessageSquare } from "lucide-react"
import { roleDisplayName } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { DialogEntry } from "@/lib/conversation-types"

function railClass(role: string): string {
  switch (role) {
    case "Lawyer":
      return "bg-chart-1"
    case "Judge":
      return "bg-chart-5"
    case "Final":
      return "bg-chart-2"
    case "Plaintiff":
      return "bg-chart-4"
    case "Defendant":
      return "bg-chart-3"
    case "Client":
      return "bg-chart-2"
    default:
      return "bg-muted-foreground"
  }
}

export function Transcript({
  messages,
  streamingText,
  endRef,
}: {
  messages: DialogEntry[]
  streamingText?: string
  endRef?: React.RefObject<HTMLDivElement | null>
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto border-y border-border">
      {messages.length === 0 && !streamingText ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          <div className="text-center">
            <MessageSquare className="mx-auto mb-2 size-8 opacity-40" />
            <p className="text-sm">还没有发言</p>
            <p className="mt-1 text-xs">发送消息或自动推进开始听证</p>
          </div>
        </div>
      ) : (
        <div className="mx-auto max-w-3xl space-y-0 px-4 py-3">
          {messages.map((msg, index) => (
            <div key={index} className="relative border-b border-border/60 py-3 pl-3">
              <div className={cn("absolute inset-y-3 left-0 w-0.5 rounded-full", railClass(msg.role))} />
              <div className="mb-1 flex items-center gap-2 text-[12px] text-muted-foreground">
                <span className="font-medium text-foreground">{roleDisplayName(msg.role)}</span>
                {msg.turn != null ? <span>#{msg.turn}</span> : null}
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.message}</div>
            </div>
          ))}
          {streamingText ? (
            <div className="relative border-b border-border/60 py-3 pl-3">
              <div className="absolute inset-y-3 left-0 w-0.5 rounded-full bg-chart-1" />
              <div className="mb-1 text-[12px] italic text-muted-foreground">正在输入…</div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {streamingText}
                <span className="ml-0.5 inline-block h-4 w-px align-text-bottom bg-foreground/70" />
              </div>
            </div>
          ) : null}
          <div ref={endRef} />
        </div>
      )}
    </div>
  )
}
