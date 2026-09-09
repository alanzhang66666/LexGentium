"use client"

import { useEffect, useState } from "react"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { listCases } from "@/lib/api"

export function CasePicker({
  value,
  onChange,
  allowCustom = true,
}: {
  value: string
  onChange: (caseId: string) => void
  allowCustom?: boolean
}) {
  const [cases, setCases] = useState<Array<{ case_id?: string; cause?: string }>>([])

  useEffect(() => {
    listCases(40)
      .then((data) => setCases(data.cases || []))
      .catch(() => setCases([]))
  }, [])

  const options = cases.filter((c) => c.case_id)
  const known = options.some((c) => c.case_id === value)

  return (
    <div className="space-y-2">
      <Select value={known ? value : "__custom__"} onValueChange={(v) => onChange(v === "__custom__" ? value : v)}>
        <SelectTrigger>
          <SelectValue placeholder="选择 1K 案件" />
        </SelectTrigger>
        <SelectContent>
          {options.map((c) => (
            <SelectItem key={c.case_id} value={c.case_id!}>
              {c.case_id}
              {c.cause ? ` · ${c.cause}` : ""}
            </SelectItem>
          ))}
          {allowCustom ? <SelectItem value="__custom__">自定义 ID</SelectItem> : null}
        </SelectContent>
      </Select>
      {allowCustom && !known ? (
        <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder="输入案例 ID" />
      ) : null}
    </div>
  )
}
