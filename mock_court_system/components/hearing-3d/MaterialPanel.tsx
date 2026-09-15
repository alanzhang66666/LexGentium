"use client"

import type { SceneState } from "./contracts"

export function MaterialPanel({ state }: { state: SceneState }) {
  const claimEntries = Object.entries(state.claims)
  const materialEntries = Object.entries(state.materials)
  return (
    <aside className="w-72 shrink-0 rounded-xl border border-white/10 bg-slate-950/85 p-4 text-sm text-white backdrop-blur">
      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">争点与材料</div>
      {state.active_issue ? (
        <div className="mb-4 rounded-lg bg-white/5 p-3">
          <div className="font-semibold">{state.active_issue.label}</div>
          <div className="mt-1 text-xs text-white/60">{state.active_issue.description}</div>
        </div>
      ) : <div className="mb-4 text-white/50">等待争点事件</div>}
      <div className="space-y-2">
        {claimEntries.length === 0 ? <div className="text-xs text-white/40">暂无主张状态</div> : claimEntries.map(([id, claim]) => (
          <div key={id} className="rounded-lg border border-white/10 p-2">
            <div className="text-xs font-semibold">{id}</div>
            <div className="mt-1 text-xs text-white/65">{String(claim.reason ?? claim.evidence_status ?? "未知")}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 border-t border-white/10 pt-3">
        <div className="mb-2 text-xs font-semibold text-cyan-300">材料引用</div>
        {materialEntries.length === 0 ? <div className="text-xs text-white/40">暂无材料引用</div> : materialEntries.map(([id, material]) => (
          <div key={id} className="mb-2 rounded-lg border border-white/10 p-2">
            <div className="text-xs font-semibold">{String(material.title ?? id)}</div>
            <div className="mt-1 text-[11px] text-white/55">版本：{String(material.version ?? "未提供")} · {String(material.availability ?? "结构引用")}</div>
            <div className="mt-1 text-[11px] text-amber-200/80">材料不可用或权限不足时不会生成下载地址。</div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-white/45">未附原始材料的结构样例不会伪造下载地址。</div>
    </aside>
  )
}
