import Link from "next/link"
import { Home, PlayCircle, BookOpen, Info, BarChart3, Database, History, MessageSquare, Activity, Swords, Settings } from "lucide-react"
import { ThemeToggle } from "@/components/theme-toggle"

export function Navigation() {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/70 backdrop-blur-2xl supports-[backdrop-filter]:bg-background/50 shadow-sm">
      <div className="container mx-auto px-4 md:px-8 py-4 md:py-5">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 md:gap-4 hover:opacity-80 transition-opacity">
            <div className="flex items-center rounded-xl bg-white px-2.5 py-1.5 shadow ring-1 ring-black/5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/branding/lexgentium-logo.png" alt="法序智演 LexGentium" className="h-7 md:h-9 w-auto" />
            </div>
            <div>
              <h1 className="hidden sm:block text-sm sm:text-base md:text-lg font-bold tracking-tight text-balance">
                基于扩展式博弈建模的多智能体协同模拟法庭系统
              </h1>
            </div>
          </Link>

          <nav className="flex items-center gap-1 md:gap-2">
            <Link
              href="/"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Home className="w-4 h-4" />
              <span className="hidden sm:inline">首页</span>
            </Link>
            <Link
              href="/simulate"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <PlayCircle className="w-4 h-4" />
              <span className="hidden sm:inline">模拟器</span>
            </Link>
            <Link
              href="/hearing-3d"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <PlayCircle className="w-4 h-4" />
              <span className="hidden sm:inline">仲裁听证 3D</span>
            </Link>
            <Link
              href="/conversation"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <MessageSquare className="w-4 h-4" />
              <span className="hidden sm:inline">对话</span>
            </Link>
            <Link
              href="/full-simulation"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Swords className="w-4 h-4" />
              <span className="hidden sm:inline">博弈</span>
            </Link>
            <Link
              href="/evaluation"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <BarChart3 className="w-4 h-4" />
              <span className="hidden sm:inline">评测</span>
            </Link>
            <Link
              href="/database"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Database className="w-4 h-4" />
              <span className="hidden sm:inline">数据库</span>
            </Link>
            <Link
              href="/api-history"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <History className="w-4 h-4" />
              <span className="hidden sm:inline">API历史</span>
            </Link>
            <Link
              href="/system"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Activity className="w-4 h-4" />
              <span className="hidden sm:inline">系统状态</span>
            </Link>
            <Link
              href="/docs"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <BookOpen className="w-4 h-4" />
              <span className="hidden sm:inline">文档</span>
            </Link>
            <Link
              href="/settings"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">设置</span>
            </Link>
            <Link
              href="/about"
              className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg hover:bg-muted transition-colors text-sm font-medium"
            >
              <Info className="w-4 h-4" />
              <span className="hidden sm:inline">关于</span>
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-primary/10 rounded-full border border-primary/20">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-xs font-semibold text-primary">在线</span>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  )
}
