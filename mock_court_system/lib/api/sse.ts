export { consumeSse, parseSseBlocks } from "@/lib/court3d/parseSse"

export async function streamJson(
  path: string,
  body: unknown,
  onEvent: (evt: Record<string, unknown>) => void | Promise<void>,
  signal?: AbortSignal,
) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
    cache: "no-store",
  })
  if (!res.ok || !res.body) {
    throw new Error(`SSE 启动失败 HTTP ${res.status}`)
  }
  const { consumeSse } = await import("@/lib/court3d/parseSse")
  await consumeSse(res, onEvent, signal)
}
