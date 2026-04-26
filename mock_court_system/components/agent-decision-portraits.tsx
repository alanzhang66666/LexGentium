import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Gavel, Scale, User, Users } from "lucide-react"
import type { ReactNode } from "react"

type Strategy = "竞争" | "合作" | "妥协" | "回避" | "迁就"

type Portrait = {
  id: string
  name: string
  role: string
  icon: ReactNode
  dominant: Strategy
  dist: Record<Strategy, number> // 0..1, sum=1
  notes: string
}

const STRATEGIES: Strategy[] = ["竞争", "合作", "妥协", "回避", "迁就"]

function Radar({ dist, accent = "hsl(var(--primary))" }: { dist: Record<Strategy, number>; accent?: string }) {
  // 纯前端 SVG 雷达图：PPT/网页清晰，且无需任何外部图片
  const size = 160
  const cx = size / 2
  const cy = size / 2
  const r = 56
  const angles = STRATEGIES.map((_, i) => (-Math.PI / 2) + (i * 2 * Math.PI) / STRATEGIES.length)

  const point = (a: number, rr: number) => [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr] as const

  const poly = angles
    .map((a, i) => {
      const v = Math.max(0, Math.min(1, dist[STRATEGIES[i]] ?? 0))
      const [x, y] = point(a, r * (0.35 + 0.65 * v))
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(" ")

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
      {/* 网格 */}
      {[0.35, 0.55, 0.75, 0.95].map((k) => {
        const ring = angles.map((a) => point(a, r * k).join(",")).join(" ")
        return <polygon key={k} points={ring} fill="none" stroke="hsl(var(--border))" strokeWidth="1" opacity="0.9" />
      })}

      {/* 轴 */}
      {angles.map((a, i) => {
        const [x2, y2] = point(a, r * 0.98)
        const [lx, ly] = point(a, r * 1.18)
        return (
          <g key={STRATEGIES[i]}>
            <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="hsl(var(--border))" strokeWidth="1" opacity="0.9" />
            <text
              x={lx}
              y={ly}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="11"
              fill="hsl(var(--muted-foreground))"
            >
              {STRATEGIES[i]}
            </text>
          </g>
        )
      })}

      {/* 画像多边形 */}
      <polygon points={poly} fill={accent} opacity="0.16" />
      <polygon points={poly} fill="none" stroke={accent} strokeWidth="2.4" />
      <circle cx={cx} cy={cy} r="2.6" fill={accent} opacity="0.9" />
    </svg>
  )
}

const PORTRAITS: Portrait[] = [
  {
    id: "cd",
    name: "CDAgent",
    role: "起诉律师（CD）",
    icon: <Scale className="w-5 h-5" />,
    dominant: "合作",
    dist: { 竞争: 0.12, 合作: 0.44, 妥协: 0.22, 回避: 0.10, 迁就: 0.12 },
    notes: "偏合作，强调证据链完整与可执行救济。",
  },
  {
    id: "dd",
    name: "DDAgent",
    role: "答辩律师（DD）",
    icon: <User className="w-5 h-5" />,
    dominant: "妥协",
    dist: { 竞争: 0.18, 合作: 0.26, 妥协: 0.32, 回避: 0.12, 迁就: 0.12 },
    notes: "以风险控制为主，倾向在关键争点上寻求折中。",
  },
  {
    id: "ci",
    name: "CIAgent",
    role: "审判长（CI）",
    icon: <Gavel className="w-5 h-5" />,
    dominant: "合作",
    dist: { 竞争: 0.10, 合作: 0.40, 妥协: 0.28, 回避: 0.12, 迁就: 0.10 },
    notes: "追求程序正义与实质公平，鼓励协商收敛。",
  },
  {
    id: "sim",
    name: "SimAgent",
    role: "当事人模拟（per-party）",
    icon: <Users className="w-5 h-5" />,
    dominant: "竞争",
    dist: { 竞争: 0.34, 合作: 0.22, 妥协: 0.22, 回避: 0.12, 迁就: 0.10 },
    notes: "更受情绪/损失厌恶影响，初期更强硬。",
  },
]

export function AgentDecisionPortraits() {
  return (
    <section className="container mx-auto px-4 md:px-8 py-10 md:py-14">
      <div className="mx-auto max-w-5xl">
        <div className="text-center space-y-2 mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-balance">四智能体决策画像</h2>
          <p className="text-sm md:text-base text-muted-foreground text-pretty">
            以 TKI 五维策略分布呈现每个智能体的决策偏好。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {PORTRAITS.map((p) => (
            <Card key={p.id} className="border-2 bg-card/95 backdrop-blur-sm">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-3">
                  <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-primary/10 border border-primary/15 text-primary">
                    {p.icon}
                  </span>
                  <div className="leading-tight">
                    <div className="text-base font-bold">{p.role}</div>
                    <div className="text-xs text-muted-foreground font-medium">{p.name}</div>
                  </div>
                  <span className="ml-auto text-xs font-semibold px-2.5 py-1 rounded-full bg-muted border">
                    主导：{p.dominant}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-col sm:flex-row gap-4 items-center sm:items-start">
                  <div className="shrink-0">
                    <Radar dist={p.dist} />
                  </div>
                  <div className="w-full space-y-3">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {STRATEGIES.map((s) => (
                        <div key={s} className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
                          <span className="text-muted-foreground">{s}</span>
                          <span className="font-semibold tabular-nums">{Math.round(p.dist[s] * 100)}%</span>
                        </div>
                      ))}
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">{p.notes}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

