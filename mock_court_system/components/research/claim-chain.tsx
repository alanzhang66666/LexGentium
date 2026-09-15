"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { CLAIM_ACTION_LABELS, CLAIM_ACTIONS, RESEARCH_DISCLAIMER, type ClaimAction, type ResearchClaimNode } from "@/lib/research"

const ACTION_ORDER: ClaimAction[] = ["assert", "ground", "rebut", "supplement", "revise", "withdraw", "admit_insufficient"]

export function ClaimChainPanel({
  claims,
  runId,
  derivedFrom,
  materialsHash,
  busy,
  error,
  onSubmit,
  onDerive,
}: {
  claims: ResearchClaimNode[]
  runId?: string
  derivedFrom?: string | null
  materialsHash?: string
  busy?: boolean
  error?: string | null
  onSubmit: (body: {
    role: string
    action: string
    fact: string
    norm: string
    reasoning: string
    claim_id?: string
    target_claim_id?: string
  }) => Promise<void>
  onDerive?: () => Promise<void>
}) {
  const [role, setRole] = useState("applicant")
  const [action, setAction] = useState<ClaimAction>("assert")
  const [fact, setFact] = useState("")
  const [norm, setNorm] = useState("")
  const [reasoning, setReasoning] = useState("")
  const [target, setTarget] = useState("")

  const handleSubmit = async () => {
    await onSubmit({
      role,
      action,
      fact,
      norm,
      reasoning,
      target_claim_id: action === "rebut" ? target || undefined : undefined,
      claim_id: action !== "assert" && action !== "ground" && action !== "rebut" ? target || undefined : undefined,
    })
    setFact("")
    setNorm("")
    setReasoning("")
  }

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-border bg-card/40 lg:w-80 lg:border-b-0 lg:border-l">
      <div className="border-b border-border px-3 py-2">
        <div className="text-[13px] font-medium">主张链</div>
        <div className="mt-0.5 break-all text-[11px] text-muted-foreground">
          {runId ? `run ${runId.slice(0, 16)}…` : "无研究运行"}
          {derivedFrom ? ` · 派生自 ${derivedFrom.slice(0, 10)}` : ""}
        </div>
        {materialsHash ? (
          <div className="mt-0.5 break-all text-[11px] text-muted-foreground">材料 {materialsHash.slice(0, 12)}</div>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-auto px-3 py-2">
        {!claims.length ? (
          <p className="text-[12px] text-muted-foreground">尚无主张。主张须同时写事实、规范与推理。</p>
        ) : (
          claims.map((claim) => (
            <div key={claim.claim_id} className="rounded-md border border-border px-2 py-1.5">
              <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                <span>{claim.role}</span>
                <span>{CLAIM_ACTION_LABELS[claim.status as ClaimAction] || claim.status}</span>
              </div>
              <ol className="mt-1 space-y-1">
                {claim.events.map((event) => (
                  <li key={event.event_id} className="text-[12px] leading-snug">
                    <span className="text-muted-foreground">
                      {CLAIM_ACTION_LABELS[event.action as ClaimAction] || event.action}
                    </span>
                    {event.reasoning ? ` · ${event.reasoning}` : ""}
                  </li>
                ))}
              </ol>
            </div>
          ))
        )}
      </div>
      <div className="space-y-2 border-t border-border px-3 py-2">
        <div className="grid grid-cols-2 gap-1">
          <select
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px]"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="applicant">申请人</option>
            <option value="respondent">被申请人</option>
            <option value="tribunal">仲裁庭</option>
            <option value="auditor">核验</option>
          </select>
          <select
            className="h-8 rounded-md border border-border bg-background px-2 text-[12px]"
            value={action}
            onChange={(e) => setAction(e.target.value as ClaimAction)}
          >
            {ACTION_ORDER.filter((item) => CLAIM_ACTIONS.includes(item)).map((item) => (
              <option key={item} value={item}>
                {CLAIM_ACTION_LABELS[item]}
              </option>
            ))}
          </select>
        </div>
        {action === "rebut" || action === "supplement" || action === "revise" || action === "withdraw" ? (
          <Input
            className="h-8 text-[12px]"
            placeholder={action === "rebut" ? "被反驳的 claim_id" : "原主张 claim_id"}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        ) : null}
        <Textarea className="min-h-14 text-[12px]" placeholder="事实依据" value={fact} onChange={(e) => setFact(e.target.value)} />
        <Textarea className="min-h-14 text-[12px]" placeholder="规范依据" value={norm} onChange={(e) => setNorm(e.target.value)} />
        <Textarea
          className="min-h-14 text-[12px]"
          placeholder="推理"
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
        />
        {error ? <p className="text-[12px] text-destructive">{error}</p> : null}
        <div className="flex gap-1">
          <Button size="sm" className="flex-1" disabled={busy} onClick={() => void handleSubmit()}>
            记录主张
          </Button>
          {onDerive ? (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void onDerive()}>
              新条件
            </Button>
          ) : null}
        </div>
        <p className="text-[11px] leading-snug text-muted-foreground">{RESEARCH_DISCLAIMER}</p>
      </div>
    </aside>
  )
}
