import { Scale, Sparkles, Shield, Zap } from "lucide-react"

interface HeroSectionProps {
  readonly title: string
  readonly subtitle: string
  readonly description: string
}

export function HeroSection({ title, subtitle, description }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden border-b bg-gradient-to-br from-background via-primary/5 to-accent/5">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px]" />

      <div className="container relative mx-auto px-4 md:px-8 py-12 md:py-20">
        <div className="mx-auto max-w-4xl text-center space-y-6">
          <div className="flex items-center justify-center gap-2 mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-primary to-accent rounded-2xl blur-2xl opacity-40 animate-pulse" />
              <div className="relative flex items-center justify-center w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-gradient-to-br from-primary via-primary to-accent shadow-2xl shadow-primary/30">
                <Scale className="w-8 h-8 md:w-10 md:h-10 text-primary-foreground" />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-balance bg-gradient-to-br from-foreground via-foreground to-foreground/70 bg-clip-text text-transparent">
              {title}
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground font-medium text-balance">{subtitle}</p>
          </div>

          <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed">
            {description}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 md:gap-6 pt-6">
            <div className="flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-full border border-primary/20">
              <Sparkles className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium text-primary">AI驱动</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-accent/10 rounded-full border border-accent/20">
              <Shield className="w-4 h-4 text-accent" />
              <span className="text-sm font-medium text-accent">安全可靠</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-full border border-border">
              <Zap className="w-4 h-4 text-foreground" />
              <span className="text-sm font-medium text-foreground">实时响应</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
