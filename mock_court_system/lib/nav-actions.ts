export type NavGroupId = "hearing" | "view" | "review" | "system"

export type NavAction = {
  id: string
  group: NavGroupId
  title: string
  description: string
  href: string | ((sessionId: string | null) => string)
  requiresSession?: boolean
}

export const NAV_GROUPS: { id: NavGroupId; label: string }[] = [
  { id: "hearing", label: "开庭" },
  { id: "view", label: "观庭" },
  { id: "review", label: "复盘" },
  { id: "system", label: "系统" },
]

export const NAV_ACTIONS: NavAction[] = [
  {
    id: "hearing-new",
    group: "hearing",
    title: "新建听证",
    description: "选场景和案号开一场",
    href: "/conversation",
  },
  {
    id: "hearing-list",
    group: "hearing",
    title: "会话列表",
    description: "已开场次与文字记录",
    href: "/conversation",
  },
  {
    id: "hearing-cd",
    group: "hearing",
    title: "申请准备",
    description: "起草申请书草稿",
    href: "/conversation?scenario=CD",
  },
  {
    id: "hearing-dd",
    group: "hearing",
    title: "答辩准备",
    description: "起草答辩书草稿",
    href: "/conversation?scenario=DD",
  },
  {
    id: "hearing-full",
    group: "hearing",
    title: "全案",
    description: "一次跑完申请到裁决",
    href: "/full-simulation",
  },
  {
    id: "hearing-mediation",
    group: "hearing",
    title: "独立调解",
    description: "五阶段 HDR，不改庭内和解",
    href: "/mediation",
  },
  {
    id: "view-session",
    group: "view",
    title: "进入本场",
    description: "打开当前会话的三维听证",
    href: (sessionId) => (sessionId ? `/court3d/${sessionId}` : "/court3d"),
    requiresSession: true,
  },
  {
    id: "view-lobby",
    group: "view",
    title: "选场大厅",
    description: "从已有会话进入观庭",
    href: "/court3d",
  },
  {
    id: "view-replay",
    group: "view",
    title: "离线回放",
    description: "不连后端回放记录",
    href: "/court3d/replay",
  },
  {
    id: "review-contrast",
    group: "review",
    title: "对照本场",
    description: "用本场记录做指标对照",
    href: (sessionId) =>
      sessionId ? `/evaluation?session=${encodeURIComponent(sessionId)}&pane=contrast` : "/evaluation?pane=contrast",
    requiresSession: true,
  },
  {
    id: "review-strategy",
    group: "review",
    title: "策略推演",
    description: "立场、收敛与反事实",
    href: (sessionId) =>
      sessionId ? `/evaluation?session=${encodeURIComponent(sessionId)}&pane=strategy` : "/evaluation?pane=strategy",
    requiresSession: true,
  },
  {
    id: "review-reports",
    group: "review",
    title: "最近报告",
    description: "已完成的对照摘要",
    href: "/evaluation?pane=contrast",
  },
  {
    id: "review-compliance",
    group: "review",
    title: "程序合规",
    description: "本场听证步骤完成情况",
    href: (sessionId) =>
      sessionId ? `/evaluation?session=${encodeURIComponent(sessionId)}&pane=compliance` : "/evaluation?pane=compliance",
    requiresSession: true,
  },
  {
    id: "system-login",
    group: "system",
    title: "登录",
    description: "测通已有配置并解锁",
    href: "/login",
  },
  {
    id: "system-register",
    group: "system",
    title: "开通",
    description: "写入模型配置并解锁",
    href: "/register",
  },
  {
    id: "system-health",
    group: "system",
    title: "健康",
    description: "后端与检索就绪状态",
    href: "/system",
  },
  {
    id: "system-llm",
    group: "system",
    title: "LLM",
    description: "模型与接口配置",
    href: "/settings",
  },
  {
    id: "system-law",
    group: "system",
    title: "法条",
    description: "检索适用条文",
    href: "/database",
  },
  {
    id: "system-history",
    group: "system",
    title: "调用记录",
    description: "近期 API 调用",
    href: "/api-history",
  },
  {
    id: "system-simulate",
    group: "system",
    title: "调试单轮",
    description: "无状态单轮模拟",
    href: "/simulate",
  },
]

export function resolveNavHref(action: NavAction, sessionId: string | null): string {
  return typeof action.href === "function" ? action.href(sessionId) : action.href
}

export function isNavActionDisabled(action: NavAction, sessionId: string | null): boolean {
  return Boolean(action.requiresSession && !sessionId)
}

export function activeNavGroup(pathname: string): NavGroupId | null {
  if (pathname.startsWith("/evaluation")) return "review"
  if (pathname.startsWith("/court3d")) return "view"
  if (
    pathname.startsWith("/conversation") ||
    pathname.startsWith("/full-simulation") ||
    pathname.startsWith("/mediation")
  ) {
    return "hearing"
  }
  if (
    pathname.startsWith("/system") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/settings") ||
    pathname.startsWith("/database") ||
    pathname.startsWith("/api-history") ||
    pathname.startsWith("/simulate")
  ) {
    return "system"
  }
  return null
}
