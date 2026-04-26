import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen, Code, HelpCircle, Zap, Link2 } from "lucide-react"
import Link from "next/link"

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="border-b bg-muted/30">
        <div className="container mx-auto px-4 md:px-8 py-8 md:py-12">
          <div className="max-w-3xl">
            <h1 className="text-3xl md:text-4xl font-bold mb-3 text-balance">文档中心</h1>
            <p className="text-base md:text-lg text-muted-foreground leading-relaxed text-pretty">
              了解如何使用系统的 API 接口与配置参数
            </p>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          <Card className="border-2 hover:border-primary/40 hover:shadow-lg transition-all">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 mb-3">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl">快速开始</CardTitle>
              <CardDescription>5分钟快速了解系统基本使用方法</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>学习如何配置基本参数、提交请求并解析响应结果。</p>
            </CardContent>
          </Card>

          <Card className="border-2 hover:border-primary/40 hover:shadow-lg transition-all">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 mb-3">
                <Code className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl" id="api">
                API 参考
              </CardTitle>
              <CardDescription>完整的 API 接口文档和参数说明</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>查看所有可用的接口端点、请求格式和响应结构。</p>
            </CardContent>
          </Card>

          <Card className="border-2 hover:border-primary/40 hover:shadow-lg transition-all">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 mb-3">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl">使用指南</CardTitle>
              <CardDescription>详细的功能说明和最佳实践</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>深入了解各个功能模块的使用方法和注意事项。</p>
            </CardContent>
          </Card>

          <Card className="border-2 hover:border-primary/40 hover:shadow-lg transition-all">
            <CardHeader>
              <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 mb-3">
                <HelpCircle className="w-6 h-6 text-white" />
              </div>
              <CardTitle className="text-xl" id="faq">
                常见问题
              </CardTitle>
              <CardDescription>快速找到常见问题的解决方案</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>浏览常见问题列表，获取即时帮助和故障排查指南。</p>
            </CardContent>
          </Card>
        </div>

        <div className="max-w-4xl mx-auto space-y-8">
          <div className="space-y-4">
            <h2 className="text-2xl md:text-3xl font-bold">前后端能力对照</h2>
            <Card className="border-2 border-primary/20">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Link2 className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">完整映射表</CardTitle>
                </div>
                <CardDescription>
                  浏览器通过 Next 同源接口（/api/*）访问 FastAPI；详见{" "}
                  <Link href="/system" className="text-primary underline-offset-4 hover:underline">
                    系统状态
                  </Link>{" "}
                  页中的表格。后端交互式文档默认在{" "}
                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs">http://localhost:8000/docs</code>
                  （需后端已启动）。
                </CardDescription>
              </CardHeader>
            </Card>
          </div>

          <div className="space-y-4">
            <h2 className="text-2xl md:text-3xl font-bold">API 端点</h2>
            <Card className="border-2">
              <CardHeader>
                <CardTitle className="font-mono text-lg">POST /api/simulate</CardTitle>
                <CardDescription>提交法律场景模拟请求</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h4 className="font-semibold mb-2 text-sm">请求体</h4>
                  <pre className="bg-muted p-4 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
                    {`{
  "scenario": "CD" | "DD" | "CI",
  "case_id": "string",
  "dialog_history": [
    {
      "turn": number,
      "role": "string",
      "message": "string"
    }
  ],
  "input_json": { /* 可选的额外参数 */ }
}`}
                  </pre>
                </div>
                <div>
                  <h4 className="font-semibold mb-2 text-sm">场景类型说明</h4>
                  <ul className="text-sm text-muted-foreground space-y-1 ml-4 list-disc">
                    <li>
                      <strong>CD</strong>: 起诉状生成 (Civil Complaint) - 生成民事起诉状
                    </li>
                    <li>
                      <strong>DD</strong>: 答辩状生成 (Defense Statement) - 生成民事答辩状
                    </li>
                    <li>
                      <strong>CI</strong>: 法庭判决 (Court Judgment) - 生成法庭判决书
                    </li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold mb-2 text-sm">响应格式</h4>
                  <pre className="bg-muted p-4 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed">
                    {`{
  "scenario": "CD" | "DD" | "CI",
  "case_id": "string",
  "response": {
    "role": "Lawyer" | "Judge" | "Final",
    "message": "string"
  }
}`}
                  </pre>
                  <p className="text-xs text-muted-foreground mt-2">
                    响应中的 <code className="bg-muted px-1 py-0.5 rounded">role</code> 字段表示角色类型：
                    <br />
                    • <strong>Lawyer</strong>: 律师角色（CD/DD场景的中间响应）
                    <br />
                    • <strong>Judge</strong>: 法官角色（CI场景的中间响应）
                    <br />
                    • <strong>Final</strong>: 最终结果（起诉状/答辩状/判决书）
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <h2 className="text-2xl md:text-3xl font-bold">环境配置</h2>
            <Card className="border-2">
              <CardHeader>
                <CardTitle>后端服务地址</CardTitle>
                <CardDescription>配置 FastAPI 后端服务的连接地址</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted p-4 rounded-lg text-xs font-mono overflow-x-auto">
                  {`BACKEND_URL=http://localhost:8000
# 可选：浏览器内「打开后端 Swagger」链接（与 BACKEND_URL 一致即可）
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`}
                </pre>
                <p className="text-sm text-muted-foreground mt-3">
                  在 <code className="bg-muted px-1.5 py-0.5 rounded text-xs">.env.local</code> 文件中设置此环境变量
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
