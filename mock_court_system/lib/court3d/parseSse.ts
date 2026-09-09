export function parseSseBlocks(buffer: string): { events: Record<string, unknown>[]; rest: string } {
  const chunks = buffer.split("\n\n")
  const rest = chunks.pop() ?? ""
  const events: Record<string, unknown>[] = []
  for (const raw of chunks) {
    const eventLine = raw.split("\n").find((l) => l.startsWith("event:"))
    const dataLine = raw.split("\n").find((l) => l.startsWith("data:"))
    if (!dataLine) continue
    try {
      const data = JSON.parse(dataLine.slice(5).trim()) as Record<string, unknown>
      if (eventLine && data.type === undefined) {
        data.type = eventLine.slice(6).trim()
      }
      events.push(data)
    } catch {
      // skip heartbeat fragments
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
  while (true) {
    if (signal?.aborted) {
      await reader.cancel()
      break
    }
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { events, rest } = parseSseBlocks(buffer)
    buffer = rest
    for (const evt of events) {
      await onEvent(evt)
    }
  }
}
