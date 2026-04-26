import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Target, Users, Lightbulb, Award } from "lucide-react"

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="border-b bg-muted/30">
        <div className="container mx-auto px-4 md:px-8 py-8 md:py-12">
          <div className="max-w-3xl">
            <h1 className="text-3xl md:text-4xl font-bold mb-3 text-balance">关于我们</h1>
            <p className="text-base md:text-lg text-muted-foreground leading-relaxed text-pretty">
              了解模拟法庭系统的使命、愿景和技术创新
            </p>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="max-w-4xl mx-auto space-y-12">
          <div className="space-y-4">
            <h2 className="text-2xl md:text-3xl font-bold">我们的使命</h2>
            <Card className="border-2">
              <CardContent className="pt-6">
                <p className="text-base text-muted-foreground leading-relaxed text-pretty">
                  模拟法庭系统致力于通过先进的人工智能技术，为法律教育、研究和实践提供高度仿真的智能化场景模拟服务。我们相信技术可以让法律学习更加高效，让法律研究更加深入，让法律实践更加精准。
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <h2 className="text-2xl md:text-3xl font-bold">核心价值</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="border-2">
                <CardHeader>
                  <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 mb-3">
                    <Target className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-xl">专业专注</CardTitle>
                  <CardDescription>深耕法律科技领域，追求卓越品质</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <p>我们专注于法律场景的精准模拟，不断优化算法和模型，确保系统的专业性和准确性。</p>
                </CardContent>
              </Card>

              <Card className="border-2">
                <CardHeader>
                  <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 mb-3">
                    <Lightbulb className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-xl">创新驱动</CardTitle>
                  <CardDescription>采用前沿技术，持续推动产品进化</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <p>基于多智能体系统和深度学习技术，我们不断探索法律AI的边界，引领行业创新。</p>
                </CardContent>
              </Card>

              <Card className="border-2">
                <CardHeader>
                  <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 mb-3">
                    <Users className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-xl">用户至上</CardTitle>
                  <CardDescription>倾听需求，提供优质服务体验</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <p>我们始终以用户需求为导向，持续优化产品功能和交互体验，让技术真正服务于实践。</p>
                </CardContent>
              </Card>

              <Card className="border-2">
                <CardHeader>
                  <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 mb-3">
                    <Award className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-xl">质量保证</CardTitle>
                  <CardDescription>严格测试，确保系统稳定可靠</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  <p>每一个功能都经过严格的测试和验证，我们承诺为用户提供稳定、安全、高效的服务。</p>
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-2xl md:text-3xl font-bold">技术架构</h2>
            <Card className="border-2">
              <CardContent className="pt-6 space-y-4">
                <div>
                  <h4 className="font-semibold mb-2">多智能体系统</h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    采用先进的多智能体协作框架，模拟法庭中的多方角色互动，包括法官、律师、当事人等，实现高度仿真的场景模拟。
                  </p>
                </div>
                <div>
                  <h4 className="font-semibold mb-2">深度学习算法</h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    基于大规模法律语料训练的深度学习模型，能够准确理解法律语境，生成专业的法律分析和建议。
                  </p>
                </div>
                <div>
                  <h4 className="font-semibold mb-2">可扩展架构</h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    采用微服务架构设计，支持灵活的功能扩展和性能优化，满足不同规模用户的需求。
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
