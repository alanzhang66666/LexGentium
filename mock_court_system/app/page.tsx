import { Button } from "@/components/ui/button"
import { FeaturesGrid } from "@/components/features-grid"
import { ArrowRight } from "lucide-react"
import { MarketingShell } from "@/components/shell"
import Link from "next/link"
import { SCENARIO_DESCRIPTIONS, SCENARIO_LABELS } from "@/lib/labels"

const HEARING_STEPS = [
  { key: "CD" as const, n: "01" },
  { key: "DD" as const, n: "02" },
  { key: "CI" as const, n: "03" },
]

const AUDIENCES = [
  { title: "教学", description: "按程序阶段走完一场仲裁听证" },
  { title: "研究", description: "会话可回溯，复盘做指标对照" },
  { title: "演练", description: "申请人、被申请人、首席仲裁员同场" },
]

export default function Home() {
  return (
    <MarketingShell>
      <section className="border-b border-border">
        <div className="mx-auto max-w-[1120px] px-4 pt-16 pb-24 md:pt-24 md:pb-32">
          <div className="grid items-end gap-16 lg:grid-cols-12">
            <div className="space-y-7 lg:col-span-6">
              <p className="text-[13px] text-muted-foreground">LexGentium 0.8</p>
              <h1 className="text-[48px] font-medium leading-[1.05] tracking-[-0.045em] md:text-[56px] lg:text-[64px]">
                国际商事仲裁听证仿真
              </h1>
              <p className="max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
                开庭、观庭、复盘共用一场会话。申请准备、答辩准备、仲裁听证按程序推进。
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild size="lg">
                  <Link href="/conversation">
                    开庭
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <Link href="/register">开通</Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <Link href="/court3d">观庭</Link>
                </Button>
                <Button asChild variant="ghost" size="lg">
                  <Link href="/evaluation">复盘</Link>
                </Button>
              </div>
            </div>
            <div className="lg:col-span-6">
              <div className="rounded-lg border border-border p-6 shadow-[0_12px_40px_rgba(0,0,0,0.08)]">
                <p className="text-[13px] text-muted-foreground">一场听证</p>
                <ol className="mt-5 space-y-0">
                  {HEARING_STEPS.map((step, index) => (
                    <li key={step.key} className="flex gap-4">
                      <div className="flex w-8 shrink-0 flex-col items-center">
                        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{step.n}</span>
                        {index < HEARING_STEPS.length - 1 ? (
                          <span className="mt-1 min-h-10 w-px flex-1 bg-border" aria-hidden />
                        ) : null}
                      </div>
                      <div className={index < HEARING_STEPS.length - 1 ? "pb-6" : ""}>
                        <div className="text-sm font-medium">{SCENARIO_LABELS[step.key]}</div>
                        <p className="mt-1 text-sm text-muted-foreground">{SCENARIO_DESCRIPTIONS[step.key]}</p>
                      </div>
                    </li>
                  ))}
                </ol>
                <p className="mt-6 text-xs text-muted-foreground">文字记录与 3D 观庭绑定同一 session_id。</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <FeaturesGrid />

      <section className="border-t border-border">
        <div className="mx-auto grid max-w-[1120px] gap-10 px-4 pt-16 pb-24 md:grid-cols-12 md:gap-16">
          <div className="md:col-span-4">
            <h2 className="text-[28px] font-medium tracking-tight">适用</h2>
            <p className="mt-3 max-w-[28ch] text-sm text-muted-foreground">教学、研究、演练共用同一条听证路径。</p>
          </div>
          <ul className="divide-y divide-border border-y border-border md:col-span-8">
            {AUDIENCES.map((item) => (
              <li key={item.title} className="flex flex-col gap-1 py-5 sm:flex-row sm:items-baseline sm:gap-8">
                <h3 className="w-24 shrink-0 text-sm font-medium">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </MarketingShell>
  )
}
