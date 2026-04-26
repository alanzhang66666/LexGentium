import { Shield, Cpu, BarChart3, Users, FileCheck, Lightbulb } from "lucide-react"
import type { LucideIcon } from "lucide-react"

interface Feature {
  readonly icon: LucideIcon
  readonly title: string
  readonly description: string
  readonly color: string
}

const FEATURES: readonly Feature[] = [
  {
    icon: Cpu,
    title: "多智能体协作",
    description: "通过扩展式博弈建模多智能体协同过程，模拟真实法庭中各方角色的互动与决策",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: Shield,
    title: "场景全覆盖",
    description: "支持起诉状生成(CD)、答辩状生成(DD)、法庭判决(CI)等多种法律场景的专业模拟",
    color: "from-purple-500 to-pink-500",
  },
  {
    icon: BarChart3,
    title: "数据可视化",
    description: "实时展示案件进展、对话历史和分析结果，让复杂信息一目了然",
    color: "from-green-500 to-emerald-500",
  },
  {
    icon: Users,
    title: "角色智能化",
    description: "AI驱动的角色系统，准确模拟律师、法官、当事人等多方视角",
    color: "from-orange-500 to-red-500",
  },
  {
    icon: FileCheck,
    title: "案例管理",
    description: "灵活的案例标识与追踪系统，支持批量处理和历史记录查询",
    color: "from-indigo-500 to-blue-500",
  },
  {
    icon: Lightbulb,
    title: "智能分析",
    description: "深度学习算法分析案情，提供专业的法律建议和策略推荐",
    color: "from-yellow-500 to-amber-500",
  },
] as const

export function FeaturesGrid() {
  return (
    <section className="container mx-auto px-4 md:px-8 py-12 md:py-16">
      <div className="text-center mb-12 md:mb-16 space-y-4">
        <h2 className="text-3xl md:text-4xl font-bold text-balance">核心功能特性</h2>
        <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed">
          集成前沿AI技术与法律专业知识，为您提供全方位的法律模拟解决方案
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
        {FEATURES.map((feature) => {
          const IconComponent = feature.icon
          return (
            <div
              key={feature.title}
              className="group relative bg-card border-2 border-border rounded-2xl p-6 md:p-8 hover:border-primary/40 hover:shadow-xl transition-all duration-300"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity" />

              <div className="relative space-y-4">
                <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-muted to-muted/50 group-hover:scale-110 transition-transform">
                  <div
                    className={`flex items-center justify-center w-12 h-12 rounded-lg bg-gradient-to-br ${feature.color}`}
                  >
                    <IconComponent className="w-6 h-6 text-white" />
                  </div>
                </div>

                <div className="space-y-2">
                  <h3 className="text-lg md:text-xl font-bold text-balance">{feature.title}</h3>
                  <p className="text-sm md:text-base text-muted-foreground leading-relaxed text-pretty">
                    {feature.description}
                  </p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
