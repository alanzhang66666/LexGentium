"use client"

import { useEffect, useState, type FormEvent } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MarketingShell } from "@/components/shell"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  defaultLlmPayload,
  describeApiError,
  getLlmConfig,
  testLlmConfig,
  type CurrentLlmConfig,
  type LlmConfigPayload,
} from "@/lib/api/config"
import { markUnlocked, writeSessionApiToken } from "@/lib/session/unlock"

export default function LoginPage() {
  const router = useRouter()
  const [current, setCurrent] = useState<CurrentLlmConfig | null>(null)
  const [loadError, setLoadError] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [provider, setProvider] = useState("deepseek")
  const [apiToken, setApiToken] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    let cancelled = false
    getLlmConfig()
      .then((data) => {
        if (cancelled) return
        setCurrent(data)
        setProvider(data.provider || "deepseek")
        setBaseUrl(data.base_url || "")
        setModel(data.model || "")
      })
      .catch((err) => {
        if (!cancelled) setLoadError(describeApiError(err, "无法读取已有配置。请确认后端已启动。"))
      })
    return () => {
      cancelled = true
    }
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

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    const payload = buildPayload()
    if (!payload.api_key || !payload.base_url || !payload.model) {
      setError("请填写模型密钥、Base URL 与模型名，以便测通已有配置。")
      return
    }
    setPending(true)
    writeSessionApiToken(apiToken)
    try {
      const result = await testLlmConfig(payload)
      if (!result.success) {
        setError(result.message || result.detail || "测通失败：鉴权失败或服务不可达。")
        return
      }
      markUnlocked()
      router.push("/conversation")
    } catch (err) {
      setError(describeApiError(err, "测通请求失败。"))
    } finally {
      setPending(false)
    }
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
            可选填写 API_TOKEN，仅存于本页会话，供后续请求附带 Authorization。未解锁也可进入工作台；密钥仍可在设置中改。
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
              </div>
            ) : loadError ? (
              <Alert variant="destructive">
                <AlertDescription>{loadError}</AlertDescription>
              </Alert>
            ) : (
              <p className="text-xs text-muted-foreground">正在读取本机配置…</p>
            )}

            <div className="space-y-2">
              <Label htmlFor="login-base-url">Base URL</Label>
              <Input
                id="login-base-url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com/v1"
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
                placeholder="deepseek-chat"
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

            <div className="space-y-2">
              <Label htmlFor="login-api-token">
                API_TOKEN <span className="font-normal text-muted-foreground">可选</span>
              </Label>
              <Input
                id="login-api-token"
                type="password"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                placeholder="仅当后端启用了接口令牌时填写"
                className="font-mono"
                autoComplete="off"
              />
            </div>

            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <Button type="submit" size="lg" className="w-full" disabled={pending}>
              {pending ? "正在测通…" : "测通并进入"}
            </Button>
          </div>
        </form>
      </section>
    </MarketingShell>
  )
}
