const UNLOCKED_KEY = "lexgentium.unlocked"
const EVENT_NAME = "lexgentium:unlock"

// 兼容清理：历史版本把 API Token 存在 sessionStorage，浏览器侧一律移除。
const LEGACY_API_TOKEN_KEY = "lexgentium.apiToken"

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

/** 软解锁只保留非敏感 UI 状态；API Token 由 BFF server-only 配置持有。 */
export function isUnlocked(): boolean {
  return readItem(UNLOCKED_KEY) === "1"
}

export function markUnlocked() {
  writeItem(UNLOCKED_KEY, "1")
  // 清除可能遗留的浏览器 token
  removeItem(LEGACY_API_TOKEN_KEY)
  notifyUnlock()
}

/** Clears the soft gate. Does not delete server `.env`. */
export function clearUnlock() {
  removeItem(UNLOCKED_KEY)
  removeItem(LEGACY_API_TOKEN_KEY)
  notifyUnlock()
}

export function subscribeUnlock(onChange: (unlocked: boolean) => void) {
  if (!canUseSessionStorage()) return () => {}
  const handler = () => onChange(isUnlocked())
  window.addEventListener(EVENT_NAME, handler)
  return () => window.removeEventListener(EVENT_NAME, handler)
}
