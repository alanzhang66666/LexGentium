"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { getConversation } from "@/lib/api/conversation"
import { writeLastSessionId } from "@/lib/session/last-session"
import type { ConversationInfo, Scenario, SessionLinks } from "@/lib/conversation-types"

interface SessionContextValue {
  sessionId: string
  info: ConversationInfo | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({
  sessionId,
  children,
}: {
  sessionId: string
  children: React.ReactNode
}) {
  const [info, setInfo] = useState<ConversationInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getConversation(sessionId)
      setInfo(data)
      writeLastSessionId(sessionId)
    } catch (e) {
      setError(e instanceof Error ? e.message : "无法加载会话")
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo(
    () => ({ sessionId, info, loading, error, refresh }),
    [sessionId, info, loading, error, refresh],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}

export function useSessionLinks(): SessionLinks {
  const { info } = useSession()
  return info?.links || {}
}

export function useSessionScenario(): Scenario {
  const { info } = useSession()
  return (info?.scenario as Scenario) || "CI"
}
