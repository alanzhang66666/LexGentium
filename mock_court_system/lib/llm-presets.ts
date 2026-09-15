export type ProviderPreset = {
  base_url: string
  model: string
  label: string
}

export const PROVIDER_PRESETS: Record<string, ProviderPreset> = {
  deepseek: {
    base_url: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    label: "DeepSeek",
  },
  openai: {
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
    label: "OpenAI",
  },
  kimi: {
    base_url: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
    label: "Kimi (Moonshot)",
  },
  qwen: {
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    label: "通义千问 (Qwen)",
  },
  siliconflow: {
    base_url: "https://api.siliconflow.cn/v1",
    model: "Pro/moonshotai/Kimi-K2-Instruct-0905",
    label: "SiliconFlow",
  },
  custom: {
    base_url: "",
    model: "",
    label: "自定义",
  },
}
