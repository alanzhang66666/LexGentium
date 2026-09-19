import { MarketingShell } from "@/components/shell"
import Link from "next/link"
import { SCENARIO_DESCRIPTIONS, SCENARIO_LABELS, ROLE_LABELS } from "@/lib/labels"

export default function DocsPage() {
  return (
    <MarketingShell>
      <section className="border-b border-border">
        <div className="mx-auto max-w-[1120px] px-4 py-16">
          <h1 className="text-[32px] font-medium tracking-tight">文档</h1>
          <p className="mt-2 text-[13px] text-muted-foreground">法序智演 · 1.0</p>
          <p className="mt-3 max-w-xl text-sm text-muted-foreground">
            一场听证一个会话：开庭 → 观庭{" "}
            <code className="font-mono text-xs">/hearing-3d</code>
            {" "}→ 复盘。浏览器只打 Next{" "}
            <code className="font-mono text-xs">/api/*</code>。先{" "}
            <Link href="/register" className="text-primary hover:underline">
              开通
            </Link>
            {" "}或{" "}
            <Link href="/login" className="text-primary hover:underline">
              登录
            </Link>
            {" "}测通模型。接口分档见{" "}
            <Link href="/system" className="text-primary hover:underline">
              系统
            </Link>
            。
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-[1120px] space-y-12 px-4 py-16">
        <div>
          <h2 className="text-lg font-medium" id="api">
            场景
          </h2>
          <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
            <li>
              <strong className="text-foreground">CD</strong> {SCENARIO_LABELS.CD} - {SCENARIO_DESCRIPTIONS.CD}
            </li>
            <li>
              <strong className="text-foreground">DD</strong> {SCENARIO_LABELS.DD} - {SCENARIO_DESCRIPTIONS.DD}
            </li>
            <li>
              <strong className="text-foreground">CI</strong> {SCENARIO_LABELS.CI} - {SCENARIO_DESCRIPTIONS.CI}
            </li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-medium">角色 ID（引擎不变）</h2>
          <ul className="mt-4 space-y-1 text-sm text-muted-foreground">
            <li>Lawyer → {ROLE_LABELS.Lawyer}</li>
            <li>Judge → {ROLE_LABELS.Judge}</li>
            <li>Plaintiff → {ROLE_LABELS.Plaintiff}</li>
            <li>Defendant → {ROLE_LABELS.Defendant}</li>
            <li>Final → {ROLE_LABELS.Final}</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-medium">实验接口</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            <code className="font-mono text-xs">POST /api/simulate</code> 是无状态单轮，不进主导航。正式路径是开庭会话
            SSE。
          </p>
          <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-xs">{`{
  "scenario": "CD" | "DD" | "CI",
  "case_id": "string",
  "dialog_history": [{ "turn": 0, "role": "Client", "message": "…" }]
}`}</pre>
        </div>

        <div>
          <h2 className="text-lg font-medium" id="faq">
            环境
          </h2>
          <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-xs">{`BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`}</pre>
        </div>
      </section>
    </MarketingShell>
  )
}
