import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FeaturesGrid } from "@/components/features-grid"
import { CheckCircle2, Zap, Users, BarChart3, Shield, ArrowRight, Code } from "lucide-react"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import { AgentDecisionPortraits } from "@/components/agent-decision-portraits"
import Link from "next/link"

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="relative overflow-hidden border-b bg-gradient-to-br from-background via-primary/5 to-accent/5">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px]" />
        <div className="container relative mx-auto px-4 md:px-8 py-10 md:py-14">
          <div className="mx-auto max-w-5xl">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              <div className="lg:col-span-5 space-y-4">
                <h2 className="text-3xl md:text-4xl font-bold text-balance">多智能体协同 · 策略可解释 · 可复现实验</h2>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 pt-2">
                  <Button asChild size="lg" className="h-11 px-7 text-base shadow-lg hover:shadow-xl group">
                    <Link href="/simulate">
                      开始模拟
                      <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="lg" className="h-11 px-7 text-base border-2 bg-transparent">
                    <Link href="/evaluation">
                      查看评测
                      <BarChart3 className="w-4 h-4 ml-2" />
                    </Link>
                  </Button>
                </div>
              </div>
              <div className="lg:col-span-7">
                <Card className="border-2 bg-card/80 backdrop-blur-sm shadow-2xl">
                  <CardContent className="p-6 md:p-7">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-semibold">概览</div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                          <span className="text-xs font-semibold text-primary">Online</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-xl border bg-muted/25 p-4">
                          <div className="text-xs text-muted-foreground">流程</div>
                          <div className="mt-1 text-sm font-semibold">CD → DD → CI</div>
                        </div>
                        <div className="rounded-xl border bg-muted/25 p-4">
                          <div className="text-xs text-muted-foreground">核心</div>
                          <div className="mt-1 text-sm font-semibold">SPNE / NE</div>
                        </div>
                        <div className="rounded-xl border bg-muted/25 p-4">
                          <div className="text-xs text-muted-foreground">验证</div>
                          <div className="mt-1 text-sm font-semibold">ESS 稳定</div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </section>

      <ScrollIndicator />

      <AgentDecisionPortraits />

      <FeaturesGrid />

      <section className="container mx-auto px-4 md:px-8 py-12 md:py-16 border-t bg-muted/30">
        <div className="text-center mb-12 space-y-3">
          <h2 className="text-3xl md:text-4xl font-bold text-balance">适用场景</h2>
          <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed">
            满足不同用户群体的专业需求
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <Card className="border-2 hover:border-primary/40 hover:shadow-xl transition-all duration-300 backdrop-blur-sm bg-card/95 group">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 mb-3 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <Users className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl">法律教学</CardTitle>
              <CardDescription>为法学院学生提供真实的模拟训练环境</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>模拟真实法庭场景</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>提供即时反馈与评估</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>支持多种案例类型</span>
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="border-2 hover:border-primary/40 hover:shadow-xl transition-all duration-300 backdrop-blur-sm bg-card/95 group">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 mb-3 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl">法律研究</CardTitle>
              <CardDescription>为研究人员提供数据分析与实验平台</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>大规模案例数据分析</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>AI决策模式研究</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>策略优化实验</span>
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="border-2 hover:border-primary/40 hover:shadow-xl transition-all duration-300 backdrop-blur-sm bg-card/95 group">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 mb-3 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl">律所培训</CardTitle>
              <CardDescription>为律师事务所提供专业培训解决方案</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>新人律师快速上手</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>庭审技能提升训练</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <span>团队协作能力培养</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="container mx-auto px-4 md:px-8 py-16 md:py-24">
        <Card className="border-2 bg-gradient-to-br from-primary/5 via-accent/5 to-background overflow-hidden relative shadow-2xl">
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px]" />
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-primary/20 to-transparent rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-accent/20 to-transparent rounded-full blur-3xl" />
          <CardContent className="relative p-8 md:p-16 text-center space-y-6">
            <div className="flex items-center justify-center">
              <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-accent shadow-2xl animate-pulse">
                <Zap className="w-8 h-8 text-primary-foreground" />
              </div>
            </div>
            <div className="space-y-3">
              <h2 className="text-3xl md:text-4xl font-bold text-balance">开始您的法律模拟之旅</h2>
              <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed">
                立即体验智能化的法律场景模拟，提升您的专业能力与实践经验
              </p>
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <Button asChild size="lg" className="h-12 px-8 text-base shadow-lg hover:shadow-xl group">
                <Link href="/simulate">
                  开始模拟
                  <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base border-2 bg-transparent">
                <Link href="/docs">
                  <Code className="w-4 h-4 mr-2" />
                  查看文档
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      <Footer />
    </div>
  )
}
