import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { clearUnlock, isUnlocked, markUnlocked } from "./unlock"

const UNLOCKED_KEY = "lexgentium.unlocked"
const LEGACY_API_TOKEN_KEY = "lexgentium.apiToken"

function installSessionStorageStub() {
  const store = new Map<string, string>()
  const storage = {
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size
    },
  }
  const windowStub = {
    dispatchEvent: () => true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }
  ;(globalThis as Record<string, unknown>).window = windowStub
  ;(globalThis as Record<string, unknown>).sessionStorage = storage
  if (typeof globalThis.CustomEvent !== "function") {
    class CustomEventStub {
      constructor(
        public type: string,
        public init?: unknown,
      ) {}
    }
    ;(globalThis as Record<string, unknown>).CustomEvent = CustomEventStub
  }
  return store
}

let store: Map<string, string>

beforeEach(() => {
  store = installSessionStorageStub()
})

afterEach(() => {
  delete (globalThis as Record<string, unknown>).window
  delete (globalThis as Record<string, unknown>).sessionStorage
})

describe("browser unlock boundary", () => {
  it("markUnlocked writes only the soft unlock marker", () => {
    markUnlocked()
    expect(store.get(UNLOCKED_KEY)).toBe("1")
    expect(isUnlocked()).toBe(true)
  })

  it("removes a legacy persisted API token on unlock", () => {
    store.set(LEGACY_API_TOKEN_KEY, "leaked-token")
    markUnlocked()
    expect(store.has(LEGACY_API_TOKEN_KEY)).toBe(false)
  })

  it("clearUnlock removes the marker and any legacy token", () => {
    store.set(UNLOCKED_KEY, "1")
    store.set(LEGACY_API_TOKEN_KEY, "leaked-token")
    clearUnlock()
    expect(isUnlocked()).toBe(false)
    expect(store.has(LEGACY_API_TOKEN_KEY)).toBe(false)
  })

  it("never stores any key containing a token", () => {
    markUnlocked()
    for (const key of store.keys()) {
      expect(key.toLowerCase()).not.toContain("token")
    }
  })
})
