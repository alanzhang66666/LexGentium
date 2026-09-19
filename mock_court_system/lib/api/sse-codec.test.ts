import { describe, expect, it } from "vitest"

import {
  decodeFrame,
  newDecodeContext,
  splitFrames,
  SseProtocolError,
} from "./sse-codec"

const OP = "op_1"
const REQ = "req_1"

function v1Frame(seq: number, type: string, extra: Record<string, unknown> = {}) {
  const env = {
    schema_version: "1",
    operation_id: OP,
    request_id: REQ,
    sequence: seq,
    type,
    ...extra,
  }
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(env)}\n\n`
}

describe("sse-codec", () => {
  it("round-trips v1 events with all fields", () => {
    const ctx = newDecodeContext(OP, REQ)
    const { frames } = splitFrames(
      v1Frame(0, "delta", { role: "Lawyer", text: "异议成立", degraded: true }),
    )
    const decoded = decodeFrame(frames[0], ctx)
    expect(decoded?.kind).toBe("v1")
    if (decoded?.kind === "v1") {
      expect(decoded.event.sequence).toBe(0)
      expect(decoded.event.type).toBe("delta")
      expect(decoded.event.text).toBe("异议成立")
      expect(decoded.event.degraded).toBe(true)
    }
  })

  it("enforces strictly increasing sequence", () => {
    const ctx = newDecodeContext(OP, REQ)
    decodeFrame(splitFrames(v1Frame(0, "start")).frames[0], ctx)
    expect(() =>
      decodeFrame(splitFrames(v1Frame(0, "delta")).frames[0], ctx),
    ).toThrowError(SseProtocolError)
  })

  it("rejects id drift and unknown types", () => {
    const ctx = newDecodeContext(OP, REQ)
    const drift = v1Frame(0, "start").replace(`"operation_id":"${OP}"`, '"operation_id":"op_X"')
    expect(() => decodeFrame(splitFrames(drift).frames[0], ctx)).toThrowError(/id_drift/)

    const ctx2 = newDecodeContext(OP, REQ)
    expect(() => decodeFrame(splitFrames(v1Frame(0, "bogus")).frames[0], ctx2)).toThrowError(
      /unknown_type/,
    )
  })

  it("dual-reads legacy events without sequence checks", () => {
    const ctx = newDecodeContext(OP, REQ)
    const legacy = `event: final\ndata: {"type":"final","payload":{"x":1}}\n\n`
    const decoded = decodeFrame(splitFrames(legacy).frames[0], ctx)
    expect(decoded?.kind).toBe("legacy")
    if (decoded?.kind === "legacy") {
      expect(decoded.event.type).toBe("final")
    }
  })

  it("blocks events after terminal", () => {
    const ctx = newDecodeContext(OP, REQ)
    decodeFrame(splitFrames(v1Frame(0, "complete")).frames[0], ctx)
    expect(ctx.terminated).toBe(true)
    expect(() =>
      decodeFrame(splitFrames(v1Frame(1, "delta")).frames[0], ctx),
    ).toThrowError(/bad_terminal/)
    // legacy 事件在 terminal 后也被忽略
    const legacy = `event: final\ndata: {"type":"final"}\n\n`
    expect(decodeFrame(splitFrames(legacy).frames[0], ctx)).toBeNull()
  })
})
