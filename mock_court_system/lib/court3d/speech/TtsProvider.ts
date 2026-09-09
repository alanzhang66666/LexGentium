export interface SpeakRequest {
  text: string
  lang: "zh-CN" | "en-US"
  voiceHint?: "male" | "female"
  rate?: number
  onBoundary?: (charIndex: number) => void
  onStart?: () => void
  onEnd?: () => void
}

export interface TtsHandle {
  cancel: () => void
}

export interface TtsProvider {
  id: string
  speak(req: SpeakRequest): TtsHandle
}

export class WebSpeechProvider implements TtsProvider {
  id = "web-speech"

  speak(req: SpeakRequest): TtsHandle {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      const t = setTimeout(() => req.onEnd?.(), Math.min(4000, 80 * req.text.length))
      return { cancel: () => clearTimeout(t) }
    }

    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(req.text)
    utter.lang = req.lang
    utter.rate = req.rate ?? (req.lang === "zh-CN" ? 0.95 : 1)
    const voices = window.speechSynthesis.getVoices()
    const picked = pickVoice(voices, req.lang, req.voiceHint)
    if (picked) utter.voice = picked

    utter.onstart = () => req.onStart?.()
    utter.onend = () => req.onEnd?.()
    utter.onerror = () => req.onEnd?.()
    utter.onboundary = (ev) => {
      if (typeof ev.charIndex === "number") req.onBoundary?.(ev.charIndex)
    }

    window.speechSynthesis.speak(utter)
    return {
      cancel: () => {
        window.speechSynthesis.cancel()
      },
    }
  }
}

export class BackendTtsProvider implements TtsProvider {
  id = "backend"

  speak(req: SpeakRequest): TtsHandle {
    // Phase-2 hook: POST /tts then play audio. Falls back to Web Speech.
    return new WebSpeechProvider().speak(req)
  }
}

function pickVoice(voices: SpeechSynthesisVoice[], lang: string, hint?: "male" | "female") {
  const langHit = voices.filter((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()))
  const pool = langHit.length ? langHit : voices
  if (!hint) return pool[0]
  const named = pool.find((v) =>
    hint === "female"
      ? /female|woman|女|hui|xiaoxiao|xiaoyi/i.test(v.name)
      : /male|man|男|yunjian|yunxi|kangkang/i.test(v.name),
  )
  return named ?? pool[0]
}
