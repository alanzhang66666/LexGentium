/**
 * SSE_Event_Codec（TypeScript 侧，与 api/services/sse.py 对称，design §4）。
 *
 * - 新格式：SseEventV1 envelope 写入 data:，sequence 同时写入 id:，
 *   type 写入 event:；sequence 从 0 严格递增。
 * - 双读兼容期：旧事件名（final/simulation_complete 等）映射为
 *   LegacyEvent，不阻断消费；新 terminal 到达后忽略后续事件。
 * - 未知类型、缺字段、operation/request ID 漂移、非递增 sequence
 *   抛 SseProtocolError，绝不产生业务事件。
 */

export const SSE_EVENT_TYPES = [
  "start",
  "heartbeat",
  "delta",
  "progress",
  "complete",
  "error",
  "cancelled",
] as const

export type SseEventType = (typeof SSE_EVENT_TYPES)[number]
export const TERMINAL_TYPES: readonly string[] = ["complete", "error", "cancelled"]

export interface SseEventV1 {
  schema_version: "1"
  operation_id: string
  request_id: string
  sequence: number
  type: SseEventType
  role?: string | null
  text?: string | null
  degraded?: boolean
  sub_stage?: string | null
  resource?: { type: string; id: string } | null
  error?: Record<string, unknown> | null
  /** 域事件载荷：迁移期携带原事件体，原始事件名在 payload.event */
  payload?: Record<string, unknown> | null
  emitted_at?: string
}

/** 旧格式直通事件（双读期） */
export interface LegacyEvent {
  legacy: true
  type: string
  data: Record<string, unknown>
}

export type DecodedEvent = { kind: "v1"; event: SseEventV1 } | { kind: "legacy"; event: LegacyEvent }

export class SseProtocolError extends Error {
  readonly kind: "unknown_type" | "missing_field" | "id_drift" | "sequence" | "bad_terminal"
  constructor(kind: SseProtocolError["kind"], detail = "") {
    super(`sse protocol error[${kind}]: ${detail}`)
    this.kind = kind
  }
}

interface RawFrame {
  id?: string
  event?: string
  data?: string
}

/** 把 SSE 文本块切成 frame 字段集 */
export function splitFrames(buffer: string): { frames: RawFrame[]; rest: string } {
  const chunks = buffer.split("\n\n")
  const rest = chunks.pop() ?? ""
  const frames: RawFrame[] = []
  for (const raw of chunks) {
    if (!raw.trim()) continue
    const frame: RawFrame = {}
    for (const line of raw.split("\n")) {
      const idx = line.indexOf(":")
      if (idx < 0) continue
      const key = line.slice(0, idx).trim()
      const value = line.slice(idx + 1).trim()
      if (key === "id") frame.id = value
      else if (key === "event") frame.event = value
      else if (key === "data") frame.data = frame.data ? `${frame.data}\n${value}` : value
    }
    frames.push(frame)
  }
  return { frames, rest }
}

export interface DecodeContext {
  operationId: string
  requestId: string
  lastSequence: number
  terminated: boolean
}

export function newDecodeContext(operationId: string, requestId: string): DecodeContext {
  return { operationId, requestId, lastSequence: -1, terminated: false }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v)
}

/** 解析单个 frame；新格式做全部不变量校验，旧格式透传为 legacy 事件。 */
export function decodeFrame(frame: RawFrame, ctx: DecodeContext): DecodedEvent | null {
  if (frame.data === undefined) {
    throw new SseProtocolError("missing_field", "data")
  }
  let env: unknown
  try {
    env = JSON.parse(frame.data)
  } catch {
    throw new SseProtocolError("missing_field", "data not json")
  }
  if (!isObject(env)) {
    throw new SseProtocolError("missing_field", "envelope not object")
  }

  // 双读：无 schema_version=1 的旧事件 → legacy 直通（不进 sequence 校验）
  if (env.schema_version !== "1") {
    const legacyType = (frame.event ?? (typeof env.type === "string" ? env.type : "message")) || "message"
    if (ctx.terminated) return null
    return { kind: "legacy", event: { legacy: true, type: legacyType, data: env } }
  }

  for (const required of ["operation_id", "request_id", "sequence", "type"] as const) {
    if (!(required in env)) {
      throw new SseProtocolError("missing_field", required)
    }
  }
  if (!SSE_EVENT_TYPES.includes(env.type as SseEventType)) {
    throw new SseProtocolError("unknown_type", String(env.type))
  }
  if (env.operation_id !== ctx.operationId) {
    throw new SseProtocolError("id_drift", "operation_id")
  }
  if (env.request_id !== ctx.requestId) {
    throw new SseProtocolError("id_drift", "request_id")
  }
  const sequence = env.sequence
  if (typeof sequence !== "number" || !Number.isInteger(sequence) || sequence < 0) {
    throw new SseProtocolError("sequence", "non-negative int required")
  }
  if (frame.id !== undefined && frame.id !== String(sequence)) {
    throw new SseProtocolError("sequence", "id field drift")
  }
  if (sequence <= ctx.lastSequence) {
    throw new SseProtocolError("sequence", "non-increasing")
  }
  if (ctx.terminated) {
    throw new SseProtocolError("bad_terminal", "event after terminal")
  }

  ctx.lastSequence = sequence
  if (TERMINAL_TYPES.includes(env.type as string)) {
    ctx.terminated = true
  }
  return { kind: "v1", event: env as unknown as SseEventV1 }
}

/** 从 Response body 消费统一流；新/旧格式都经 decodeFrame 分发。 */
export async function consumeSseStream(
  response: Response,
  ctx: DecodeContext,
  onEvent: (decoded: DecodedEvent) => void | Promise<void>,
  signal?: AbortSignal,
): Promise<void> {
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
    const { frames, rest } = splitFrames(buffer)
    buffer = rest
    for (const frame of frames) {
      const decoded = decodeFrame(frame, ctx)
      if (decoded) await onEvent(decoded)
    }
  }
  if (buffer.trim()) {
    const { frames } = splitFrames(buffer + "\n\n")
    for (const frame of frames) {
      const decoded = decodeFrame(frame, ctx)
      if (decoded) await onEvent(decoded)
    }
  }
}
