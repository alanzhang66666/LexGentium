import { cn } from "@/lib/utils"

const ALT = "法序智演 LexGentium"

export function BrandLockup({
  className,
  heightClass = "h-[18px]",
}: {
  className?: string
  heightClass?: string
}) {
  return (
    <span className={cn("inline-flex items-center", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/branding/lexgentium-logo.png" alt={ALT} className={cn("w-auto dark:hidden", heightClass)} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/branding/lexgentium-logo-dark.png" alt="" className={cn("hidden w-auto dark:block", heightClass)} />
    </span>
  )
}

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex size-5 shrink-0 items-center justify-center", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon-light-32x32.png" alt={ALT} className="size-5 dark:hidden" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon-dark-32x32.png" alt="" className="hidden size-5 dark:block" />
    </span>
  )
}
