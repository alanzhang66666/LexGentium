import { MarketingShell } from "@/components/shell"

export default function AboutPage() {
  return (
    <MarketingShell>
      <section className="border-b border-border">
        <div className="mx-auto max-w-[680px] px-4 pt-16 pb-20">
          <h1 className="text-[40px] font-medium leading-[1.1] tracking-[-0.03em]">关于</h1>
          <p className="mt-4 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            法序智演 LexGentium 是国际商事仲裁研究平台，不是泛用模拟法庭演示页。
          </p>
        </div>
      </section>
      <section className="mx-auto max-w-[680px] space-y-12 px-4 pt-16 pb-24">
        <div>
          <h2 className="text-lg font-medium">做什么</h2>
          <p className="mt-3 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            用一场会话跑完申请准备、答辩准备与仲裁听证。文字开庭与 3D 观庭绑定同一
            session，复盘对申请书、答辩书、裁决草稿做指标对照。
          </p>
        </div>
        <div>
          <h2 className="text-lg font-medium">称谓</h2>
          <p className="mt-3 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            界面写首席仲裁员、申请人、被申请人。引擎仍用 Judge / Plaintiff 等 ID。
          </p>
        </div>
        <div>
          <h2 className="text-lg font-medium">观庭</h2>
          <p className="mt-3 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            观庭是 <code className="font-mono text-xs">/hearing-3d</code>：程序化占位 Phase A，可挂本场
            session。正式 VRM 未到，不在本页承诺成片。旧 <code className="font-mono text-xs">/court3d</code>{" "}
            会重定向过来。
          </p>
        </div>
      </section>
    </MarketingShell>
  )
}
