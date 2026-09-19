import { describe, expect, it } from "vitest"
import { consumeSse, parseSseBlocks } from "./parseSse"

describe("SSE parsing", () => {
  it("parses multiple CRLF events and keeps an incomplete trailing block", () => {
    const { events, rest } = parseSseBlocks(
      'event: delta\r\ndata: {"type":"delta","text":"A"}\r\n\r\nevent: final\r\ndata: {"type":"final","response":{"role":"Arbitrator"}}\r\n\r\nevent: pending\r\ndata: {"type":"pending"}',
    )
    expect(events).toEqual([
      { type: "delta", text: "A" },
      { type: "final", response: { role: "Arbitrator" } },
    ])
    expect(rest).toContain("pending")
  })

  it("reassembles UTF-8 split across transport chunks and dispatches the final unterminated event", async () => {
    const encoder = new TextEncoder()
    const bytes = encoder.encode('data: {"type":"final","text":"证据已核验"}')
    const splitAt = bytes.indexOf(0xE8) + 1
    const chunks = [bytes.slice(0, splitAt), bytes.slice(splitAt, splitAt + 2), bytes.slice(splitAt + 2)]
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(chunk))
        controller.close()
      },
    })
    const events: Record<string, unknown>[] = []
    await consumeSse(new Response(body), (event) => { events.push(event) })
    expect(events).toEqual([{ type: "final", text: "证据已核验" }])
  })
})
