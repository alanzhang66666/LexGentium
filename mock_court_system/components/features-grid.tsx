import { Box, FileCheck, Gavel, MessageSquare, Scale, ScrollText } from "lucide-react"
import type { LucideIcon } from "lucide-react"

const FEATURED: { icon: LucideIcon; title: string; description: string }[] = [
  {
    icon: FileCheck,
    title: "申请准备",
    description: "围绕案号起草申请书草稿，进入听证前可单独成场。",
  },
  {
    icon: ScrollText,
    title: "答辩准备",
    description: "针对申请主张生成答辩书草稿，与申请场共用案件索引。",
  },
]

const REST: { icon: LucideIcon; title: string; description: string; span: string }[] = [
  {
    icon: Gavel,
    title: "仲裁听证",
    description: "核对出庭、陈述举证、抗辩询问、和解与裁决按阶段推进。",
    span: "md:col-span-7",
  },
  {
    icon: Scale,
    title: "程序可视化",
    description: "阶段与下一发言写在顶栏，角色 ID 不变，展示用仲裁称谓。",
    span: "md:col-span-5",
  },
  {
    icon: MessageSquare,
    title: "会话可回溯",
    description: "一场听证一个 session_id，文字记录、全案与复盘可回写链接。",
    span: "md:col-span-5",
  },
  {
    icon: Box,
    title: "3D 观庭",
    description: "观庭走 /hearing-3d：程序化占位 Phase A，可挂本场 session。非正式 VRM。",
    span: "md:col-span-7",
  },
]

export function FeaturesGrid() {
  return (
    <section className="mx-auto max-w-[1120px] px-4 pt-16 pb-20">
      <h2 className="mb-10 text-[28px] font-medium tracking-tight">能力</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {FEATURED.map((feature) => {
          const Icon = feature.icon
          return (
            <div key={feature.title} className="rounded-lg border border-border p-7">
              <Icon className="mb-5 size-4 text-muted-foreground" />
              <h3 className="text-lg font-medium tracking-tight">{feature.title}</h3>
              <p className="mt-2 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
            </div>
          )
        })}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-12">
        {REST.map((feature) => {
          const Icon = feature.icon
          return (
            <div key={feature.title} className={`rounded-lg border border-border p-5 ${feature.span}`}>
              <Icon className="mb-3 size-4 text-muted-foreground" />
              <h3 className="text-sm font-medium">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
            </div>
          )
        })}
      </div>
    </section>
  )
}
