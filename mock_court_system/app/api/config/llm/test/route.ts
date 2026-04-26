import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/config/llm/test", {
    method: "POST",
    body: await request.json(),
    label: "llm-config-test",
    timeoutMs: 35000,
    timeoutMessage: "测试超时（>35s），请检查 base_url 是否正确。",
  })
}

