"use client"

import { useRef, useState, type FormEvent } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MarketingShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { JourneyError } from "@/components/journey/states"
import { defaultLlmPayload, saveLlmConfig, testLlmConfig, type LlmConfigPayload } from "@/lib/api/config"
import { PROVIDER_PRESETS } from "@/lib/llm-presets"
import { markUnlocked } from "@/lib/session/unlock"

export default function RegisterPage() {
  const router = useRouter()
  const [provider, setProvider] = useState("deepseek")
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState(PROVIDER_PRESETS.deepseek.base_url)
  const [model, setModel] = useState(PROVIDER_PRESETS.deepseek.model)
  const [showKey, setShowKey] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const opIdRef = useRef<string | null>(null)

  const handleProviderChange = (next: string) => {
    setProvider(next)
    const preset = PROVIDER_PRESETS[next]
    if (preset && next !== "custom") {
      setBaseUrl(preset.base_url)
      setModel(preset.model)
    }
  }

  const buildPayload = (): LlmConfigPayload =>
    defaultLlmPayload({
      provider,
      api_key: apiKey.trim(),
      base_url: baseUrl.trim(),
      model: model.trim(),
    })

  const runProvision = async (operationId: string) => {
    const payload = buildPayload()
    if (!payload.api_key || !payload.base_url || !payload.model) {
      setError("请填写服务商、密钥、地址与模型名。无密钥时开通会失败，不会白屏。")
      return
    }
    setPending(true)
    try {
      const saved = await saveLlmConfig(payload, operationId)
      if (!saved.success) {
        setError(saved.detail || saved.message || "写入配置失败。")
        return
      }
      const tested = await testLlmConfig(payload, operationId)
      if (!tested.success) {
        setError(tested.message || tested.detail || "配置已写入，但测通失败。可改密钥后重试，或前往登录再测。")
        return
      }
      markUnlocked()
      router.push("/conversation")
    } catch (err) {
      setError(err)
    } finally {
      setPending(false)
    }
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    // 每次显式提交生成新 Operation ID；JourneyError 的显式重试复用它
    opIdRef.current = crypto.randomUUID()
    await runProvision(opIdRef.current)
  }

  return (
    <MarketingShell>
      <section className="mx-auto grid max-w-[1120px] gap-12 px-4 py-16 md:grid-cols-2 md:items-start md:py-24">
        <div>
          <p className="text-xs tracking-[0.08em] text-muted-foreground">LEXGENTIUM</p>
          <h1 className="mt-3 text-[40px] font-medium leading-[1.1] tracking-[-0.03em]">开通</h1>
          <p className="mt-4 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">
            一场听证绑定一个 session。本页首次写入供应商预设与密钥，再测通，不建用户表。
          </p>
          <p className="mt-3 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">
            后端接口令牌由服务端环境统一注入，浏览器不持有 Token。工作台未解锁也可进入；此后仍可在设置中改密钥。
          </p>
          <p className="mt-8 text-sm text-muted-foreground">
            已有配置？
            <Link href="/login" className="ml-1 text-primary hover:underline">
              登录
            </Link>
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-[6px] border border-border bg-card p-6"
          noValidate
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="register-provider">服务商预设</Label>
              <Select value={provider} onValueChange={handleProviderChange}>
                <SelectTrigger id="register-provider" className="w-full">
                  <SelectValue placeholder="选择服务商" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PROVIDER_PRESETS).map(([key, preset]) => (
                    <SelectItem key={key} value={key}>
                      {preset.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="register-base-url">Base URL</Label>
              <Input
                id="register-base-url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com/v1"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="register-model">模型名</Label>
              <Input
                id="register-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="deepseek-chat"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="register-api-key">模型密钥</Label>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setShowKey((v) => !v)}
                >
                  {showKey ? "隐藏" : "显示"}
                </button>
              </div>
              <Input
                id="register-api-key"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-…"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <JourneyError
              error={error}
              fallback="开通失败：无法写入或测通配置。"
              onRetry={
                opIdRef.current
                  ? () => void runProvision(opIdRef.current as string)
                  : undefined
              }
              busy={pending}
            />

            <Button type="submit" size="lg" className="w-full" disabled={pending}>
              {pending ? "正在写入并测通…" : "开通"}
            </Button>
          </div>
        </form>
      </section>
    </MarketingShell>
  )
}
