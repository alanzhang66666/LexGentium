import Link from "next/link"
import { MarketingShell } from "@/components/shell"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-[680px] px-4 pt-24 pb-32">
        <p className="font-mono text-[13px] tabular-nums text-muted-foreground">404</p>
        <h1 className="mt-4 text-[40px] font-medium leading-[1.1] tracking-[-0.03em]">没有这个页面</h1>
        <p className="mt-4 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
          地址不存在或已改过。回首页看产品说明，或直接开庭开始一场听证。
        </p>
        <div className="mt-8 flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/">回首页</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/conversation">开庭</Link>
          </Button>
        </div>
      </section>
    </MarketingShell>
  )
}
