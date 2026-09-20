import type { ConversationSummary } from "@/lib/conversation-types"

export const YINGFAN_DEMO_CASE_ID = "enf-us-yingfan-amazon-001"

export function resolveDemoOpeningPath(sessions: ConversationSummary[]): string {
  const candidates = sessions
    .filter(
      (session) =>
        session.scenario === "CI" &&
        session.case_id === YINGFAN_DEMO_CASE_ID &&
        session.message_count > 0,
    )
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))

  const session = candidates[0]
  return session
    ? `/conversation/${encodeURIComponent(session.session_id)}?view=opening`
    : "/conversation"
}
