"use client"

import { ACTOR_LABELS, AUDIT_STATUS_LABELS, STAGE_LABELS, STRATEGY_LABELS, SUB_STAGE_LABELS } from "@/lib/labels"
import type { Actor } from "@/lib/court3d/protocol"
import type { PerformanceState } from "@/lib/court3d/performanceStore"
import type { CastDefinition, SkinId } from "@/lib/court3d/cast"

export function Hud({
  state,
  cast,
  skin,
  showStrategy = false,
}: {
  state: PerformanceState
  cast: CastDefinition
  skin: SkinId
  showStrategy?: boolean
}) {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-lg border border-border bg-card/90 px-3 py-2 backdrop-blur-md">
          <div className="text-[12px] text-muted-foreground">{cast.title}</div>
          <div className="text-[13px] font-medium">
            {STAGE_LABELS[state.stage ?? ""] ?? state.stage}{" "}
            {state.subStage ? `· ${SUB_STAGE_LABELS[state.subStage] ?? state.subStage}` : ""}
          </div>
          <div className="text-[12px] text-muted-foreground">
            下一发言：{state.nextSpeaker ? ACTOR_LABELS[state.nextSpeaker] : "-"}
          </div>
        </div>
        {showStrategy || state.auditStatus ? (
          <div className="space-y-1 rounded-lg border border-border bg-card/90 px-3 py-2 text-[12px] backdrop-blur-md">
            {showStrategy ? (
              <>
                <div>申请人策略：{STRATEGY_LABELS[state.hud.plaintiffStrategy ?? state.actors.plaintiff_party.strategy]}</div>
                <div>被申请人策略：{STRATEGY_LABELS[state.hud.defendantStrategy ?? state.actors.defendant_party.strategy]}</div>
                {state.hud.convergence != null ? <div>收敛：{(state.hud.convergence * 100).toFixed(1)}%</div> : null}
                {state.hud.score?.degraded ? (
                  <div className="text-warning">评分降级（离线占位，非真实 LLM 结果）</div>
                ) : state.hud.score?.plaintiff_win_rate != null ? (
                  <div>申请人胜率：{(state.hud.score.plaintiff_win_rate * 100).toFixed(0)}%</div>
                ) : null}
              </>
            ) : null}
            {state.auditStatus ? (
              <div>
                溯源：{AUDIT_STATUS_LABELS[state.auditStatus]}
                {state.auditStatus === "unknown" ? "（未知态不发言）" : ""}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mx-auto max-w-3xl space-y-2">
        {state.degraded ? (
          <div className="rounded-md border border-border bg-card px-3 py-1 text-center text-[12px] text-warning">
            当前为离线兜底回复，不是真实智能体推理
          </div>
        ) : null}
        {state.subtitle ? (
          <div className="rounded-lg border border-border bg-card/90 px-4 py-3 text-center backdrop-blur-md">
            <div className="mb-1 text-[11px] tracking-wide text-muted-foreground">
              {state.subtitleActor ? nameOf(cast, state.subtitleActor, skin) : ""} ·{" "}
              {state.subtitleKind === "relay" ? "口译" : state.subtitleKind === "scripted" ? "程序" : "发言"}
            </div>
            <div className="text-sm leading-relaxed">{state.subtitle}</div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function nameOf(cast: CastDefinition, actor: Actor, skin: SkinId) {
  return cast.roles[actor]?.skins[skin]?.name ?? ACTOR_LABELS[actor]
}
