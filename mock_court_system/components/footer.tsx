import Link from "next/link"
import { RESEARCH_DISCLAIMER } from "@/lib/research"
import { APP_VERSION } from "@/lib/version"

export function Footer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <footer className="border-t border-border">
        <div className="mx-auto flex min-h-10 max-w-none flex-wrap items-center justify-between gap-2 px-4 py-1.5 text-xs text-muted-foreground">
          <span>法序智演 · {APP_VERSION}｜国际商事仲裁研究平台</span>
          <span className="max-w-[42rem] text-right leading-snug">{RESEARCH_DISCLAIMER}</span>
        </div>
      </footer>
    )
  }

  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-[1120px] px-4 py-12">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="space-y-2">
            <p className="text-sm font-medium">法序智演 LexGentium</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              国际商事仲裁研究平台。开庭、观庭、复盘同一会话。
            </p>
          </div>
          <div className="space-y-3">
            <h3 className="text-[13px] font-medium">产品</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/conversation" className="text-muted-foreground hover:text-foreground">
                  开庭
                </Link>
              </li>
              <li>
                <Link href="/hearing-3d" className="text-muted-foreground hover:text-foreground">
                  观庭
                </Link>
              </li>
              <li>
                <Link href="/evaluation" className="text-muted-foreground hover:text-foreground">
                  复盘
                </Link>
              </li>
              <li>
                <Link href="/system" className="text-muted-foreground hover:text-foreground">
                  系统
                </Link>
              </li>
            </ul>
          </div>
          <div className="space-y-3">
            <h3 className="text-[13px] font-medium">说明</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/docs" className="text-muted-foreground hover:text-foreground">
                  文档
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-muted-foreground hover:text-foreground">
                  关于
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-10 border-t border-border pt-6 text-xs text-muted-foreground">
          <p>{RESEARCH_DISCLAIMER}</p>
          <p className="mt-2">© 2026 法序智演 LexGentium</p>
        </div>
      </div>
    </footer>
  )
}
