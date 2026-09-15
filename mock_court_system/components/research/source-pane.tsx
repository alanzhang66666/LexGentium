"use client"

import { useEffect, useMemo } from "react"
import type { SourceAnchor } from "@/lib/research"
import { cn } from "@/lib/utils"

export function sourceDomId(sourceId: string): string {
  return `source-${sourceId}`
}

export function scrollToSourceId(sourceId: string): boolean {
  const node = document.getElementById(sourceDomId(sourceId))
  if (!node) return false
  node.scrollIntoView({ behavior: "smooth", block: "center" })
  return true
}

type Span = { start: number; end: number; source_id: string }

function resolveSpan(text: string, anchor: SourceAnchor): Span | null {
  if (typeof anchor.start_offset === "number") {
    const end = typeof anchor.end_offset === "number" ? anchor.end_offset : text.length
    if (end > anchor.start_offset) {
      return { start: anchor.start_offset, end, source_id: anchor.source_id }
    }
  }
  if (anchor.quote) {
    const idx = text.indexOf(anchor.quote)
    if (idx >= 0) {
      return { start: idx, end: idx + anchor.quote.length, source_id: anchor.source_id }
    }
  }
  if (anchor.locator) {
    const token = `[${anchor.locator}]`
    const idx = text.indexOf(token)
    if (idx >= 0) {
      const lineEnd = text.indexOf("\n", idx)
      return {
        start: idx,
        end: lineEnd >= 0 ? lineEnd : Math.min(text.length, idx + token.length + 160),
        source_id: anchor.source_id,
      }
    }
  }
  return null
}

function pickSpans(text: string, anchors: SourceAnchor[], selectedId: string | null): Span[] {
  const resolved = anchors
    .map((anchor) => resolveSpan(text, anchor))
    .filter((span): span is Span => Boolean(span))
    .sort((a, b) => {
      if (a.source_id === selectedId) return -1
      if (b.source_id === selectedId) return 1
      return a.start - b.start || b.end - a.end
    })
  const taken: Span[] = []
  for (const span of resolved) {
    const hit = taken.findIndex((item) => span.start < item.end && span.end > item.start)
    if (hit >= 0) {
      if (span.source_id === selectedId) taken[hit] = span
      continue
    }
    taken.push(span)
  }
  return taken.sort((a, b) => a.start - b.start)
}

export function SourceDocument({
  text,
  anchors,
  selectedSourceId,
  onSelectSource,
}: {
  text: string
  anchors: SourceAnchor[]
  selectedSourceId: string | null
  onSelectSource: (sourceId: string) => void
}) {
  const spans = useMemo(() => pickSpans(text, anchors, selectedSourceId), [text, anchors, selectedSourceId])

  useEffect(() => {
    if (!selectedSourceId) return
    const timer = window.setTimeout(() => {
      scrollToSourceId(selectedSourceId)
    }, 40)
    return () => window.clearTimeout(timer)
  }, [selectedSourceId, text])

  const parts: Array<{ key: string; text: string; sourceId?: string }> = []
  let cursor = 0
  spans.forEach((span, index) => {
    if (span.start > cursor) {
      parts.push({ key: `t-${cursor}`, text: text.slice(cursor, span.start) })
    }
    parts.push({
      key: `s-${span.source_id}-${index}`,
      text: text.slice(span.start, span.end),
      sourceId: span.source_id,
    })
    cursor = span.end
  })
  if (cursor < text.length) {
    parts.push({ key: `t-${cursor}-end`, text: text.slice(cursor) })
  }

  return (
    <pre className="whitespace-pre-wrap break-words font-sans text-[13px] leading-6 text-foreground">
      {parts.map((part) =>
        part.sourceId ? (
          <mark
            key={part.key}
            id={sourceDomId(part.sourceId)}
            data-source-id={part.sourceId}
            onClick={() => onSelectSource(part.sourceId!)}
            className={cn(
              "cursor-pointer rounded-sm px-0.5 transition-colors",
              part.sourceId === selectedSourceId
                ? "bg-primary/25 text-foreground ring-1 ring-primary/50"
                : "bg-amber-500/15 hover:bg-amber-500/25",
            )}
          >
            {part.text}
          </mark>
        ) : (
          <span key={part.key}>{part.text}</span>
        ),
      )}
    </pre>
  )
}
