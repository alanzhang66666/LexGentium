"use client"

import { FastForward, Loader2, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ROLE_LABELS, roleDisplayName } from "@/lib/labels"

export function Composer({
  scenario,
  isFinished,
  isLoading,
  isAdvancing,
  inputMessage,
  selectedRole,
  advanceRounds,
  onInputChange,
  onRoleChange,
  onAdvanceRoundsChange,
  onSend,
  onAdvance,
  onStop,
}: {
  scenario: string
  isFinished: boolean
  isLoading: boolean
  isAdvancing: boolean
  inputMessage: string
  selectedRole: string
  advanceRounds: number
  onInputChange: (value: string) => void
  onRoleChange: (value: string) => void
  onAdvanceRoundsChange: (value: number) => void
  onSend: () => void
  onAdvance: () => void
  onStop: () => void
}) {
  const roles =
    scenario === "CI"
      ? [
          { value: "Plaintiff", label: ROLE_LABELS.Plaintiff },
          { value: "Defendant", label: ROLE_LABELS.Defendant },
        ]
      : [{ value: "Client", label: ROLE_LABELS.Client }]

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <div className="mx-auto flex max-w-3xl flex-col gap-2">
        {!isFinished ? (
          <div className="flex flex-wrap items-center gap-2">
            <Select value={String(advanceRounds)} onValueChange={(v) => onAdvanceRoundsChange(Number(v))}>
              <SelectTrigger size="sm" className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 5, 8, 10].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} 轮
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="secondary" size="sm" onClick={onAdvance} disabled={isAdvancing || isLoading}>
              {isAdvancing ? <Loader2 className="size-3.5 animate-spin" /> : <FastForward className="size-3.5" />}
              自动推进
            </Button>
          </div>
        ) : null}

        <div className="flex items-center gap-2">
          {scenario === "CI" && !isFinished ? (
            <Select value={selectedRole} onValueChange={onRoleChange}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roles.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          <Input
            value={inputMessage}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                onSend()
              }
            }}
            placeholder={isFinished ? "听证已结束" : `以${roleDisplayName(selectedRole || "Client")}身份发言…`}
            disabled={isLoading || isFinished || isAdvancing}
            className="flex-1"
          />
          <Button onClick={onSend} disabled={isLoading || !inputMessage.trim() || isFinished || isAdvancing}>
            {isLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
            发送
          </Button>
          {isLoading ? (
            <Button variant="outline" onClick={onStop}>
              停止
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
