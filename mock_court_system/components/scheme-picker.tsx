"use client"

import { Check } from "lucide-react"
import { useColorScheme, type ColorScheme } from "@/components/theme-provider"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

const SCHEME_OPTIONS: { id: ColorScheme; label: string; description: string }[] = [
  { id: "ink", label: "墨庭", description: "近黑藏青，工作台默认" },
  { id: "parchment", label: "卷宗", description: "纸色卷宗，默认偏亮" },
  { id: "seal", label: "朱印", description: "暖墨底，印泥红" },
]

export function SchemePicker() {
  const { scheme, setScheme } = useColorScheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "rounded-md px-2 py-1.5 text-[13px] font-medium outline-none",
          "text-muted-foreground hover:bg-secondary hover:text-foreground",
          "focus-visible:ring-1 focus-visible:ring-ring",
        )}
        aria-label="配色"
      >
        配色
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>配色</DropdownMenuLabel>
        {SCHEME_OPTIONS.map((option) => {
          const selected = scheme === option.id
          return (
            <DropdownMenuItem
              key={option.id}
              onSelect={() => {
                setScheme(option.id)
              }}
            >
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-medium">{option.label}</span>
                <span className="text-[12px] font-normal text-muted-foreground">{option.description}</span>
              </span>
              <Check className={cn("mt-0.5 size-3.5 shrink-0", selected ? "opacity-100" : "opacity-0")} />
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
