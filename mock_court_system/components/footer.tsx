import Link from "next/link"

export function Footer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <footer className="border-t border-border">
        <div className="mx-auto flex h-10 max-w-none items-center justify-between px-4 text-xs text-muted-foreground">
          <span>LexGentium｜国际商事仲裁听证仿真</span>
          <span>© 2026</span>
        </div>
      </footer>
    )
  }

  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-[1120px] px-4 py-12">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="space-y-2">
            <p className="text-sm font-medium">LexGentium</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              国际商事仲裁听证仿真。开庭、观庭、复盘同一会话。
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
                <Link href="/court3d" className="text-muted-foreground hover:text-foreground">
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
        <div className="mt-10 border-t border-border pt-6 text-xs text-muted-foreground">© 2026 LexGentium</div>
      </div>
    </footer>
  )
}
