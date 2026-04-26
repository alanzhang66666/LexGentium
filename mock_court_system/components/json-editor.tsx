"use client"

import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { FileJson, CheckCircle2, AlertCircle } from "lucide-react"
import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"

interface JsonEditorProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
  required?: boolean
  helpText?: string
}

export function JsonEditor({
  label,
  value,
  onChange,
  placeholder,
  rows = 6,
  required = false,
  helpText,
}: JsonEditorProps) {
  const [isValid, setIsValid] = useState<boolean | null>(null)
  const [errorDetail, setErrorDetail] = useState<string>("")

  useEffect(() => {
    if (!value.trim()) {
      setIsValid(null)
      setErrorDetail("")
      return
    }

    try {
      JSON.parse(value)
      setIsValid(true)
      setErrorDetail("")
    } catch (error) {
      setIsValid(false)
      setErrorDetail(error instanceof Error ? error.message : "JSON 格式错误")
    }
  }, [value])

  return (
    <div className="space-y-3">
      <Label htmlFor={label} className="text-sm font-semibold flex items-center gap-2">
        <div
          className={cn("w-1.5 h-1.5 rounded-full", required ? "bg-primary animate-pulse" : "bg-muted-foreground/40")}
        />
        {label}
        {!required && <span className="text-xs font-normal text-muted-foreground">(可选)</span>}
      </Label>
      <div className="relative">
        <Textarea
          id={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          className={cn(
            "font-mono text-xs resize-none border-2 transition-all leading-relaxed pr-10",
            isValid === true && "border-accent/50 focus:border-accent bg-accent/5",
            isValid === false && "border-destructive/50 focus:border-destructive bg-destructive/5",
            isValid === null && "hover:border-primary/50 focus:border-primary",
          )}
          placeholder={placeholder}
          aria-invalid={isValid === false}
          aria-describedby={helpText ? `${label}-help` : undefined}
        />
        {isValid !== null && (
          <div className="absolute top-3 right-3 pointer-events-none">
            {isValid ? (
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-accent/20">
                <CheckCircle2 className="w-4 h-4 text-accent" />
              </div>
            ) : (
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-destructive/20">
                <AlertCircle className="w-4 h-4 text-destructive" />
              </div>
            )}
          </div>
        )}
      </div>
      {isValid === false && errorDetail && (
        <div className="flex items-start gap-2 px-3 py-2 bg-destructive/10 border border-destructive/30 rounded-lg text-xs text-destructive animate-in slide-in-from-top-1">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span className="font-medium">{errorDetail}</span>
        </div>
      )}
      {helpText && (
        <div
          id={`${label}-help`}
          className="text-xs text-muted-foreground flex items-center gap-2 bg-muted/50 px-3 py-2 rounded-lg"
        >
          <FileJson className="w-3.5 h-3.5 text-primary shrink-0" />
          {helpText}
        </div>
      )}
    </div>
  )
}
