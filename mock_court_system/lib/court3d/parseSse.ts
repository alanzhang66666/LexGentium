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
