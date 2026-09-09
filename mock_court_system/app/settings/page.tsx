"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import {
  Settings,
  Key,
  Link2,
  Cpu,
  CheckCircle2,
  XCircle,
  Loader2,
  Save,
  FlaskConical,
  Eye,
  EyeOff,
  RefreshCcw,
} from "lucide-react"
import { PROVIDER_PRESETS } from "@/lib/llm-presets"
import { clientAuthHeaders } from "@/lib/session/unlock"

interface LLMConfig {
  provider: string
  api_key: string
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  timeout: number
}

interface CurrentConfig {
  provider: string
  api_key_masked: string
  api_key_set: boolean
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  timeout: number
  chat_model_ready: boolean
}

export default function SettingsPage() {
  const [currentConfig, setCurrentConfig] = useState<CurrentConfig | null>(null)
  const [loadingCurrent, setLoadingCurrent] = useState(true)

  const [provider, setProvider] = useState("custom")
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [temperature, setTemperature] = useState("0.1")
  const [maxTokens, setMaxTokens] = useState("4096")
  const [timeout, setTimeout_] = useState("60")
  const [showKey, setShowKey] = useState(false)

  const [testStatus, setTestStatus] = useState<"idle" | "loading" | "success" | "fail">("idle")
  const [testMessage, setTestMessage] = useState("")
  const [testReply, setTestReply] = useState("")

  const [saveStatus, setSaveStatus] = useState<"idle" | "loading" | "success" | "fail">("idle")
  const [saveMessage, setSaveMessage] = useState("")

  useEffect(() => {
    fetchCurrentConfig()
  }, [])

  const fetchCurrentConfig = async () => {
    setLoadingCurrent(true)
    try {
      const res = await fetch("/api/config/llm", { headers: { ...clientAuthHeaders() } })
      if (res.ok) {
        const data: CurrentConfig = await res.json()
        setCurrentConfig(data)
        setProvider(data.provider || "custom")
        setBaseUrl(data.base_url || "")
        setModel(data.model || "")
        setTemperature(String(data.temperature ?? 0.1))
        setMaxTokens(String(data.max_tokens ?? 4096))
        setTimeout_(String(data.timeout ?? 60))
      }
    } catch {
      // ignore
    } finally {
      setLoadingCurrent(false)
    }
  }

  const handleProviderChange = (p: string) => {
    setProvider(p)
    if (p !== "custom" && PROVIDER_PRESETS[p]) {
      const preset = PROVIDER_PRESETS[p]
      setBaseUrl(preset.base_url)
      setModel(preset.model)
    }
  }

  const buildPayload = (): LLMConfig => ({
    provider,
    api_key: apiKey,
    base_url: baseUrl,
    model,
    temperature: parseFloat(temperature) || 0.1,
    max_tokens: parseInt(maxTokens) || 4096,
    timeout: parseInt(timeout) || 60,
  })

  const handleTest = async () => {
    if (!apiKey || !baseUrl || !model) {
      setTestStatus("fail")
      setTestMessage("请填写 API Key、Base URL 和模型名")
      setTestReply("")
      return
    }
    setTestStatus("loading")
    setTestMessage("正在测试连接...")
    setTestReply("")
    try {
      const res = await fetch("/api/config/llm/test", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...clientAuthHeaders() },
        body: JSON.stringify(buildPayload()),
      })
      const data = await res.json()
      if (data.success) {
        setTestStatus("success")
        setTestMessage(data.message || "连接成功")
        setTestReply(data.reply || "")
      } else {
        setTestStatus("fail")
        setTestMessage(data.message || "连接失败")
        setTestReply("")
      }
    } catch (err) {
      setTestStatus("fail")
      setTestMessage(err instanceof Error ? err.message : "请求失败")
      setTestReply("")
    }
  }

  const handleSave = async () => {
    if (!apiKey || !baseUrl || !model) {
      setSaveStatus("fail")
      setSaveMessage("请填写 API Key、Base URL 和模型名")
      return
    }
    setSaveStatus("loading")
    setSaveMessage("正在保存并重新初始化...")
    try {
      const res = await fetch("/api/config/llm", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...clientAuthHeaders() },
        body: JSON.stringify(buildPayload()),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setSaveStatus("success")
        setSaveMessage(data.message || "保存成功")
        await fetchCurrentConfig()
      } else {
        setSaveStatus("fail")
        setSaveMessage(data.detail || data.message || "保存失败")
      }
    } catch (err) {
      setSaveStatus("fail")
      setSaveMessage(err instanceof Error ? err.message : "请求失败")
    }
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">设置</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            配置兼容 OpenAI 协议的模型地址与密钥。
          </p>
        </div>
        <div className="mx-auto max-w-2xl space-y-6">

          {/* 当前状态卡片 */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Settings className="w-5 h-5" />
                当前运行配置
                <Button variant="ghost" size="sm" onClick={fetchCurrentConfig} disabled={loadingCurrent} className="ml-auto">
                  <RefreshCcw className={`w-4 h-4 ${loadingCurrent ? "animate-spin" : ""}`} />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingCurrent ? (
                <div className="flex items-center gap-2 text-muted-foreground text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  加载中...
                </div>
              ) : currentConfig ? (
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    {currentConfig.chat_model_ready ? (
                      <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                    )}
                    <span className={currentConfig.chat_model_ready ? "text-green-700 dark:text-green-400 font-medium" : "text-red-600 dark:text-red-400 font-medium"}>
                      {currentConfig.chat_model_ready ? "LLM 已就绪" : "LLM 未配置或配置无效"}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-3 text-muted-foreground">
                    <span>服务商</span><span className="text-foreground font-mono">{currentConfig.provider}</span>
                    <span>模型</span><span className="text-foreground font-mono">{currentConfig.model || "未设置"}</span>
                    <span>API Key</span><span className="text-foreground font-mono">{currentConfig.api_key_set ? currentConfig.api_key_masked : "未设置"}</span>
                    <span>Base URL</span><span className="text-foreground font-mono text-xs break-all">{currentConfig.base_url || "未设置"}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">无法获取后端配置，请确认后端已启动</p>
              )}
            </CardContent>
          </Card>

          {/* 配置表单 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="w-5 h-5" />
                配置新的 LLM
              </CardTitle>
              <CardDescription>
                填写完成后先"测试连接"，确认无误再"保存并应用"
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">

              {/* 服务商选择 */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  服务商预设
                </Label>
                <Select value={provider} onValueChange={handleProviderChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择服务商..." />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(PROVIDER_PRESETS).map(([key, preset]) => (
                      <SelectItem key={key} value={key}>
                        {preset.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">选择预设会自动填充 Base URL 和模型名</p>
              </div>

              {/* Base URL */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Link2 className="w-4 h-4" />
                  Base URL <span className="text-red-500">*</span>
                </Label>
                <Input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.deepseek.com/v1"
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  API 调用地址，须包含 <code>/v1</code>，兼容 OpenAI Chat Completions 接口
                </p>
              </div>

              {/* API Key */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Key className="w-4 h-4" />
                  API Key <span className="text-red-500">*</span>
                </Label>
                <div className="relative">
                  <Input
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="font-mono text-sm pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-muted-foreground">Key 会加密脱敏存储，页面刷新后不显示明文</p>
              </div>

              {/* 模型名 */}
              <div className="space-y-2">
                <Label>
                  模型名 <span className="text-red-500">*</span>
                </Label>
                <Input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="deepseek-chat / gpt-4o / ..."
                  className="font-mono text-sm"
                />
              </div>

              {/* 高级参数（可折叠行） */}
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-2">
                  <Label className="text-xs">Temperature</Label>
                  <Input
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                    placeholder="0.1"
                    className="font-mono text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Max Tokens</Label>
                  <Input
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(e.target.value)}
                    placeholder="4096"
                    className="font-mono text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">超时 (秒)</Label>
                  <Input
                    value={timeout}
                    onChange={(e) => setTimeout_(e.target.value)}
                    placeholder="60"
                    className="font-mono text-sm"
                  />
                </div>
              </div>

              {/* 测试结果 */}
              {testStatus !== "idle" && (
                <Alert
                  className={
                    testStatus === "success"
                      ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                      : testStatus === "fail"
                        ? "border-red-500 bg-red-50 dark:bg-red-950/30"
                        : ""
                  }
                >
                  <div className="flex items-start gap-2">
                    {testStatus === "loading" && <Loader2 className="w-4 h-4 animate-spin mt-0.5 shrink-0" />}
                    {testStatus === "success" && <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />}
                    {testStatus === "fail" && <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />}
                    <AlertDescription className="text-sm">
                      <span className="font-medium">{testMessage}</span>
                      {testReply && (
                        <div className="mt-1 text-xs text-muted-foreground border-t pt-1">
                          模型回复: {testReply}
                        </div>
                      )}
                    </AlertDescription>
                  </div>
                </Alert>
              )}

              {/* 保存结果 */}
              {saveStatus !== "idle" && (
                <Alert
                  className={
                    saveStatus === "success"
                      ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                      : saveStatus === "fail"
                        ? "border-red-500 bg-red-50 dark:bg-red-950/30"
                        : ""
                  }
                >
                  <div className="flex items-start gap-2">
                    {saveStatus === "loading" && <Loader2 className="w-4 h-4 animate-spin mt-0.5 shrink-0" />}
                    {saveStatus === "success" && <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />}
                    {saveStatus === "fail" && <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />}
                    <AlertDescription className="text-sm font-medium">{saveMessage}</AlertDescription>
                  </div>
                </Alert>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={handleTest}
                  disabled={testStatus === "loading" || saveStatus === "loading"}
                  className="flex-1"
                >
                  {testStatus === "loading" ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />测试中...</>
                  ) : (
                    <><FlaskConical className="w-4 h-4 mr-2" />测试连接</>
                  )}
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={saveStatus === "loading" || testStatus === "loading"}
                  className="flex-1"
                >
                  {saveStatus === "loading" ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />保存中...</>
                  ) : (
                    <><Save className="w-4 h-4 mr-2" />保存并应用</>
                  )}
                </Button>
              </div>

              <p className="text-xs text-muted-foreground text-center">
                "保存并应用"会立即重新初始化所有 Agent，并将配置写入 <code>.env</code> 文件以便重启后生效
              </p>
            </CardContent>
          </Card>

          {/* 常用服务商参考 */}
          <Card className="border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">常用服务商参考</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {Object.entries(PROVIDER_PRESETS).filter(([k]) => k !== "custom").map(([, p]) => (
                  <div key={p.label} className="flex items-center gap-3 text-xs">
                    <span className="w-28 font-medium shrink-0">{p.label}</span>
                    <code className="text-muted-foreground flex-1 truncate">{p.base_url}</code>
                    <code className="text-muted-foreground shrink-0">{p.model}</code>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

        </div>
      </main>
    </WorkbenchShell>
  )
}
