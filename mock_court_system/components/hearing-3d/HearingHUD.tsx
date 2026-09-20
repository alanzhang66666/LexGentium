"use client"

import type { SceneState } from "./contracts"
import { castMemberForActor } from "./cast-manifest"

export function hearingSourceLabel(
  sourceType: SceneState["source_type"],
  hasSession = false,
): "本场运行" | "待接入" {
  return sourceType === "backend_run" || hasSession ? "本场运行" : "待接入"
}

export function hearingActorLabel(actorId: string | null | undefined): string {
  const member = castMemberForActor(actorId)
  return member ? `${member.label} · ${member.name}` : actorId ?? "听证现场"
}

export function HearingHUD({
  state,
  professional = false,
  hasSession = false,
}: {
  state: SceneState
  professional?: boolean
  hasSession?: boolean
}) {
  const sourceLabel = hearingSourceLabel(state.source_type, Boolean(state.session_id) || hasSession)
  const subtitleActorId = state.subtitle?.actor_id ?? state.active_actor_id
  return (
    <div className="pointer-events-none absolute inset-0 p-4 text-white">
      <div className="flex items-start justify-between gap-4">
        <div className="rounded-xl border border-white/15 bg-slate-950/75 px-4 py-3 backdrop-blur">
          <div className="text-xs uppercase tracking-[0.25em] text-cyan-300">观庭</div>
          <div className="mt-1 text-lg font-semibold">{state.stage?.label ?? "等待听证开始"}</div>
          <div className="text-xs text-white/60">{state.active_issue?.label ?? "暂无当前争点"}</div>
        </div>
        <div className="rounded-lg bg-amber-500/90 px-3 py-2 text-xs font-semibold text-slate-950">
          {sourceLabel}
        </div>
      </div>
      {state.subtitle && (
        <div className="absolute bottom-20 left-1/2 w-[min(760px,90vw)] -translate-x-1/2 rounded-xl bg-slate-950/90 px-5 py-4 text-center shadow-2xl backdrop-blur">
          <div className="text-xs text-cyan-300">{hearingActorLabel(subtitleActorId)} · #{state.current_seq}</div>
          <div className="mt-1 text-lg leading-relaxed">{state.subtitle.zh}</div>
          {state.subtitle.en && <div className="mt-1 text-sm text-white/60">{state.subtitle.en}</div>}
        </div>
      )}
      {professional && (
        <div className="pointer-events-auto absolute bottom-4 left-4 max-w-[420px] rounded-lg border border-white/10 bg-slate-950/80 p-3 text-xs backdrop-blur">
          <div>seq: {state.current_seq} / {state.latest_seq}</div>
          <div>session: {state.session_id ?? "-"}</div>
          <div>actor: {state.active_actor_id ?? "-"}</div>
          <div>status: {state.status}</div>
          {state.reasoning_meta && (
            <div className={`mt-2 rounded border px-2 py-1 ${state.reasoning_meta.judgment_status === "ok" ? "border-emerald-400/30 text-emerald-200" : "border-amber-400/30 text-amber-200"}`}>
              <div>推理状态：{state.reasoning_meta.judgment_status ?? "unknown"}</div>
              {state.reasoning_meta.citation_report && <div>法条核验：{state.reasoning_meta.citation_report.verified ?? 0}/{state.reasoning_meta.citation_report.checked ?? 0} 已验证</div>}
              {(state.reasoning_meta.citation_report?.unverified?.length ?? 0) > 0 && <div>未验证法条：{state.reasoning_meta.citation_report?.unverified?.join("、")}</div>}
              {(state.reasoning_meta.case_warnings?.length ?? 0) > 0 && <div>案件告警：{state.reasoning_meta.case_warnings?.join("；")}</div>}
            </div>
          )}
          {state.warnings.length > 0 && <div className="mt-1 text-amber-300">{state.warnings.join("; ")}</div>}
        </div>
      )}
    </div>
  )
}
