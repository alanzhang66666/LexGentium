import type { ReactNode } from "react"
import { Footer } from "@/components/footer"
import { Navigation } from "@/components/navigation"

export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div id="content" tabIndex={-1}>
        {children}
      </div>
      <Footer />
    </div>
  )
}

export function WorkbenchShell({
  children,
  footer = true,
}: {
  children: ReactNode
  footer?: boolean
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navigation compact />
      <div id="content" tabIndex={-1} className="flex min-h-0 flex-1 flex-col">
        {children}
      </div>
      {footer ? <Footer compact /> : null}
    </div>
  )
}
