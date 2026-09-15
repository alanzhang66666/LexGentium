const STORAGE_KEY = "lexgentium.lastSessionId"
const EVENT_NAME = "lexgentium:last-session"

export function readLastSessionId(): string | null {
  if (typeof window === "undefined") return null
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeLastSessionId(sessionId: string) {
  if (typeof window === "undefined" || !sessionId) return
  try {
    sessionStorage.setItem(STORAGE_KEY, sessionId)
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: sessionId }))
  } catch {
    /* sessionStorage may be blocked */
  }
}

export function subscribeLastSession(onChange: (sessionId: string | null) => void) {
  if (typeof window === "undefined") return () => {}
  const handler = () => onChange(readLastSessionId())
  window.addEventListener(EVENT_NAME, handler)
  return () => window.removeEventListener(EVENT_NAME, handler)
}
