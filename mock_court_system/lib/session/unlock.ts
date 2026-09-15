const UNLOCKED_KEY = "lexgentium.unlocked"
const API_TOKEN_KEY = "lexgentium.apiToken"
const EVENT_NAME = "lexgentium:unlock"

function canUseSessionStorage(): boolean {
  return typeof window !== "undefined"
}

function readItem(key: string): string | null {
  if (!canUseSessionStorage()) return null
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function writeItem(key: string, value: string) {
  if (!canUseSessionStorage()) return
  try {
    sessionStorage.setItem(key, value)
  } catch {
    /* sessionStorage may be blocked */
  }
}

function removeItem(key: string) {
  if (!canUseSessionStorage()) return
  try {
    sessionStorage.removeItem(key)
  } catch {
    /* sessionStorage may be blocked */
  }
}

function notifyUnlock() {
  if (!canUseSessionStorage()) return
  window.dispatchEvent(new CustomEvent(EVENT_NAME))
}

export function isUnlocked(): boolean {
  return readItem(UNLOCKED_KEY) === "1"
}

export function readSessionApiToken(): string {
  return (readItem(API_TOKEN_KEY) || "").trim()
}

export function writeSessionApiToken(token: string) {
  const trimmed = token.trim()
  if (trimmed) writeItem(API_TOKEN_KEY, trimmed)
  else removeItem(API_TOKEN_KEY)
  notifyUnlock()
}

export function markUnlocked(apiToken?: string) {
  writeItem(UNLOCKED_KEY, "1")
  if (apiToken !== undefined) {
    const trimmed = apiToken.trim()
    if (trimmed) writeItem(API_TOKEN_KEY, trimmed)
  }
  notifyUnlock()
}

/** Clears the soft gate and in-memory token. Does not delete server `.env`. */
export function clearUnlock() {
  removeItem(UNLOCKED_KEY)
  removeItem(API_TOKEN_KEY)
  notifyUnlock()
}

export function clientAuthHeaders(): Record<string, string> {
  const token = readSessionApiToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

export function subscribeUnlock(onChange: (unlocked: boolean) => void) {
  if (!canUseSessionStorage()) return () => {}
  const handler = () => onChange(isUnlocked())
  window.addEventListener(EVENT_NAME, handler)
  return () => window.removeEventListener(EVENT_NAME, handler)
}
