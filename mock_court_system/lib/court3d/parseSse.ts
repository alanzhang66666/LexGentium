/**
 * SseEventV1 envelope → 旧域事件形状（双读期翻译层）。
 * envelope.payload 即原事件体，payload.event 是原事件名。
 */
function envelopeToLegacy(env: Record<string, unknown>): Record<string, unknown> {
  const payload = (env.payload ?? {}) as Record<string, unknown>
  const out: Record<string, unknown> = { ...payload }
  out.type = (typeof payload.event === "string" && payload.event) || (env.type as string)
  out.sequence = env.sequence
  out.operation_id = env.operation_id
  out.request_id = env.request_id
  if (env.text != null && out.text === undefined) out.text = env.text
  if (env.role != null && out.role === undefined) out.role = env.role
  if (env.sub_stage != null && out.sub_stage === undefined) out.sub_stage = env.sub_stage
  if (env.degraded !== undefined && out.degraded === undefined) out.degraded = env.degraded
  if (env.type === "error" && out.message === undefined) {
    const err = env.error as Record<string, unknown> | null | undefined
    out.message = err?.message ?? err?.code ?? "stream error"
  }
  return out
}

export function parseSseBlocks(buffer: string): { events: Record<string, unknown>[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
  const chunks = normalized.split("\n\n")
  const rest = chunks.pop() ?? ""
  const events: Record<string, unknown>[] = []
  for (const raw of chunks) {
    const lines = raw.split("\n")
    const eventLine = lines.find((line) => line.startsWith("event:"))
    const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).replace(/^ /, ""))
    if (!dataLines.length) continue
    try {
      const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>
      if (data.schema_version === "1") {
        events.push(envelopeToLegacy(data))
        continue
      }
      if (eventLine && data.type === undefined) data.type = eventLine.slice(6).trim()
      events.push(data)
    } catch {
      // Ignore comments, heartbeats, and malformed event payloads.
    }
  }
  return { events, rest }
}

export async function consumeSse(
  response: Response,
  onEvent: (evt: Record<string, unknown>) => void | Promise<void>,
  signal?: AbortSignal,
) {
  if (!response.body) throw new Error("SSE 无响应体")
  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""
  const dispatch = async (input: string) => {
    const { events, rest } = parseSseBlocks(input)
    buffer = rest
    for (const evt of events) await onEvent(evt)
  }
  while (true) {
    if (signal?.aborted) {
      await reader.cancel()
      return
    }
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    await dispatch(buffer)
  }
  buffer += decoder.decode()
  if (buffer.trim()) await dispatch(`${buffer}\n\n`)
}
