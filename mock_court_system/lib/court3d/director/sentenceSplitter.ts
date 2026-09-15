const SENTENCE_END = /([。！？!?；;]|\n{2,})/g
const MAX_SPEAK_CHARS = 80

export interface SplitResult {
  sentences: string[]
  remainder: string
}

export function pushDelta(buffer: string, delta: string): SplitResult {
  const text = `${buffer}${delta}`
  return flushComplete(text)
}

export function flushComplete(text: string): SplitResult {
  const sentences: string[] = []
  let last = 0
  SENTENCE_END.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = SENTENCE_END.exec(text)) !== null) {
    const end = match.index + match[0].length
    const piece = text.slice(last, end).trim()
    if (piece) sentences.push(...clipLong(piece))
    last = end
  }
  return { sentences, remainder: text.slice(last) }
}

export function flushAll(text: string): string[] {
  const { sentences, remainder } = flushComplete(text)
  const tail = remainder.trim()
  if (!tail) return sentences
  return [...sentences, ...clipLong(tail)]
}

function clipLong(sentence: string): string[] {
  if (sentence.length <= MAX_SPEAK_CHARS) return [sentence]
  const first = sentence.slice(0, MAX_SPEAK_CHARS).replace(/[，,、]\s*$/, "") + "……"
  return [first]
}
