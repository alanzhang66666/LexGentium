"use client"

import { useEffect, useRef, useState, type FormEvent } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MarketingShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { JourneyError } from "@/components/journey/states"
import {
  defaultLlmPayload,
  getLlmConfig,
  testLlmConfig,
  type CurrentLlmConfig,
  type LlmConfigPayload,
} from "@/lib/api/config"
import { markUnlocked } from "@/lib/session/unlock"

export default function LoginPage() {
  const router = useRouter()
  const [current, setCurrent] = useState<CurrentLlmConfig | null>(null)
  const [loadError, setLoadError] = useState<unknown>(null)
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [provider, setProvider] = useState("deepseek")
  const [showKey, setShowKey] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const opIdRef = useRef<string | null>(null)

  const loadCurrent = () => {
    getLlmConfig()
      .then((data) => {
        setCurrent(data)
        setProvider(data.provider || "deepseek")
        setBaseUrl(data.base_url || "")
        setModel(data.model || "")
        setApiKey(data.demo_mode ? "sk-demo-deepseek-v41-flash" : "")
      })
      .catch((err) => setLoadError(err))
  }

  useEffect(() => {
    loadCurrent()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const buildPayload = (): LlmConfigPayload =>
    defaultLlmPayload({
      provider,
      api_key: apiKey.trim(),
      base_url: baseUrl.trim(),
      model: model.trim(),
      temperature: current?.temperature ?? 0.1,
      max_tokens: current?.max_tokens ?? 4096,
      timeout: current?.timeout ?? 60,
    })

  const runTest = async (operationId: string) => {
    const payload = buildPayload()
    if ((!payload.api_key && !current?.demo_mode) || !payload.base_url || !payload.model) {
      setError("请填写模型密钥、Base URL 与模型名，以便测通已有配置。")
      return
    }
    setPending(true)
    try {
      const result = await testLlmConfig(payload, operationId)
      if (!result.success) {
        setError(result.message || result.detail || "测通失败：鉴权失败或服务不可达。")
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
    await runTest(opIdRef.current)
  }

  return (
    <MarketingShell>
      <section className="mx-auto grid max-w-[1120px] gap-12 px-4 py-16 md:grid-cols-2 md:items-start md:py-24">
        <div>
          <p className="text-xs tracking-[0.08em] text-muted-foreground">LEXGENTIUM</p>
          <h1 className="mt-3 text-[40px] font-medium leading-[1.1] tracking-[-0.03em]">登录</h1>
          <p className="mt-4 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">
            一场听证绑定一个 session。本页测通已写入的模型配置，不建用户表。
          </p>
          <p className="mt-3 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">
            后端接口令牌由服务端环境统一注入，浏览器不持有 Token。未解锁也可进入工作台；密钥仍可在设置中改。
          </p>
          <p className="mt-8 text-sm text-muted-foreground">
            尚未写入配置？
            <Link href="/register" className="ml-1 text-primary hover:underline">
              开通
            </Link>
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-[6px] border border-border bg-card p-6"
          noValidate
        >
          <div className="space-y-4">
            {current ? (
              <div className="rounded-[6px] border border-border bg-background px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
                <span className="text-foreground">已写入</span>
                {" · "}
                {current.provider || "未标服务商"}
                {" · "}
                {current.model || "未设模型"}
                {" · "}
                {current.api_key_set ? current.api_key_masked : "密钥未设置"}
                {" · "}
                {current.chat_model_ready ? "已连接" : "未测通"}
              </div>
            ) : loadError ? (
              <JourneyError
                error={loadError}
                fallback="无法读取已有配置。请确认后端已启动。"
                onRetry={() => {
                  setLoadError(null)
                  loadCurrent()
                }}
              />
            ) : (
              <p className="text-xs text-muted-foreground">正在读取本机配置…</p>
            )}

            <div className="space-y-2">
              <Label htmlFor="login-base-url">Base URL</Label>
              <Input
                id="login-base-url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="login-model">模型名</Label>
              <Input
                id="login-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="deepseek-flash"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="login-api-key">模型密钥</Label>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setShowKey((v) => !v)}
                >
                  {showKey ? "隐藏" : "显示"}
                </button>
              </div>
              <Input
                id="login-api-key"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="用于 POST /api/config/llm/test"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            <JourneyError
              error={error}
              fallback="测通请求失败。"
              onRetry={
                opIdRef.current
                  ? () => void runTest(opIdRef.current as string)
                  : undefined
              }
              busy={pending}
            />

            <Button type="submit" size="lg" className="w-full" disabled={pending}>
              {pending ? "正在测通…" : "测通并进入"}
            </Button>
          </div>
        </form>
      </section>
    </MarketingShell>
  )
}
