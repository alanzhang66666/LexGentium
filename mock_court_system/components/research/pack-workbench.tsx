"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { ReviewBadge } from "@/components/research/review-badge"
import { SourceDocument, scrollToSourceId } from "@/components/research/source-pane"
import {
  COLUMN_LABELS,
  COLUMN_ORDER,
  DATASET_LABELS,
  REVIEW_STATE_LABELS,
  TASK_TYPE_LABELS,
  formatChangeValue,
} from "@/components/research/labels"
import { describeApiError } from "@/lib/api/config"
import {
  getAnnotatedPack,
  listResearchChangelog,
  patchResearchField,
  patchResearchReview,
  type ResearchChangeEntry,
  type ResearchDocument,
} from "@/lib/api/research"
import {
  REVIEW_STATES,
  stripReference,
  type InputContract,
  type ResearchPack,
  type ReviewState,
  type SourceAnchor,
} from "@/lib/research"
import { cn } from "@/lib/utils"

const ACTOR_KEY = "research-annotator"

type AnnotField = {
  field_path: string
  item_id: string
  group: string
  groupLabel: string
  title: string
  text: string
  source_ids: string[]
  review_state: ReviewState
  notes?: string
  extras?: { label: string; text: string }[]
}

function packIdentity(
  pack: ResearchPack,
): Pick<InputContract, "dataset_id" | "cluster_id" | "pack_version" | "task_type"> {
  return {
    dataset_id: pack.dataset_id,
    cluster_id: pack.cluster_id,
    pack_version: pack.pack_version,
    task_type: pack.task_type,
  }
}

function asReview(value?: string | null): ReviewState {
  return REVIEW_STATES.includes(value as ReviewState) ? (value as ReviewState) : "pending"
}

function collectFields(pack: ResearchPack): AnnotField[] {
  const fields: AnnotField[] = []
  for (const fact of pack.procedural_facts ?? []) {
    fields.push({
      field_path: `procedural_facts/${fact.item_id}`,
      item_id: fact.item_id,
      group: "procedural_facts",
      groupLabel: COLUMN_LABELS.procedural_facts,
      title: fact.field_key,
      text: fact.value,
      source_ids: fact.source_ids ?? [],
      review_state: asReview(fact.review_state),
      notes: fact.notes,
    })
  }
  for (const claim of pack.party_claims ?? []) {
    fields.push({
      field_path: `party_claims/${claim.item_id}`,
      item_id: claim.item_id,
      group: "party_claims",
      groupLabel: COLUMN_LABELS.party_claims,
      title: `${claim.party} · ${claim.item_id}`,
      text: claim.claim_text,
      source_ids: claim.source_ids ?? [],
      review_state: asReview(claim.review_state),
      notes: claim.notes,
      extras: [
        { label: "事实", text: claim.facts || "" },
        { label: "规范", text: claim.norms || "" },
        { label: "推理", text: claim.reasoning || "" },
      ].filter((item) => item.text),
    })
  }
  for (const finding of pack.court_findings ?? []) {
    fields.push({
      field_path: `court_findings/${finding.item_id}`,
      item_id: finding.item_id,
      group: "court_findings",
      groupLabel: COLUMN_LABELS.court_findings,
      title: finding.item_id,
      text: finding.finding,
      source_ids: finding.source_ids ?? [],
      review_state: asReview(finding.review_state),
      notes: finding.notes,
      extras: finding.reasons ? [{ label: "理由", text: finding.reasons }] : [],
    })
  }
  for (const basis of pack.legal_bases ?? []) {
    fields.push({
      field_path: `legal_bases/${basis.item_id}`,
      item_id: basis.item_id,
      group: "legal_bases",
      groupLabel: COLUMN_LABELS.legal_bases,
      title: `${basis.rule_id}@${basis.rule_version}`,
      text: basis.citation || basis.application_note || "",
      source_ids: basis.source_ids ?? [],
      review_state: asReview(basis.review_state),
      notes: basis.notes,
      extras: basis.application_note ? [{ label: "适用说明", text: basis.application_note }] : [],
    })
  }
  for (const gap of pack.material_gaps ?? []) {
    fields.push({
      field_path: `material_gaps/${gap.gap_id}`,
      item_id: gap.gap_id,
      group: "material_gaps",
      groupLabel: COLUMN_LABELS.material_gaps,
      title: gap.related_field || gap.gap_id,
      text: gap.description,
      source_ids: [],
      review_state: asReview(gap.review_state),
      notes: gap.notes,
    })
  }
  if (pack.task_labels.task_type === "cisg_article79") {
    for (const element of pack.task_labels.elements ?? []) {
      fields.push({
        field_path: `task_labels.elements/${element.element_id}`,
        item_id: element.element_id,
        group: "task_labels",
        groupLabel: "第79条要素",
        title: element.label,
        text: element.value || element.satisfied || "",
        source_ids: element.source_ids ?? [],
        review_state: asReview(element.review_state),
        notes: element.notes,
        extras: [{ label: "成立", text: element.satisfied || "unknown" }],
      })
    }
    fields.push({
      field_path: "task_labels/conclusion_label",
      item_id: "conclusion_label",
      group: "task_labels",
      groupLabel: "第79条要素",
      title: "结论标签",
      text: pack.task_labels.conclusion_label || "unknown",
      source_ids: [],
      review_state: asReview(pack.task_labels.review_state),
      notes: pack.task_labels.conclusion_note,
    })
  } else {
    fields.push(
      {
        field_path: "task_labels/enforcement_forum",
        item_id: "enforcement_forum",
        group: "task_labels",
        groupLabel: "执行任务标签",
        title: "执行法域",
        text: pack.task_labels.enforcement_forum || "",
        source_ids: [],
        review_state: asReview(pack.task_labels.review_state),
      },
      {
        field_path: "task_labels/procedure_type",
        item_id: "procedure_type",
        group: "task_labels",
        groupLabel: "执行任务标签",
        title: "程序类型",
        text: pack.task_labels.procedure_type || "",
        source_ids: [],
        review_state: asReview(pack.task_labels.review_state),
      },
    )
    if (pack.task_labels.convention_issues?.length) {
      fields.push({
        field_path: "task_labels/convention_issues",
        item_id: "convention_issues",
        group: "task_labels",
        groupLabel: "执行任务标签",
        title: "公约争点",
        text: pack.task_labels.convention_issues.join("、"),
        source_ids: [],
        review_state: asReview(pack.task_labels.review_state),
      })
    }
  }
  return fields
}

function documentForSource(anchors: SourceAnchor[], sourceId: string | null): string | null {
  if (!sourceId) return null
  return anchors.find((anchor) => anchor.source_id === sourceId)?.document_id ?? null
}

export function PackWorkbench({ dataset, cluster }: { dataset: string; cluster: string }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialSource = searchParams.get("source")
  const initialField = searchParams.get("field")

  const [pack, setPack] = useState<ResearchPack | null>(null)
  const [documents, setDocuments] = useState<ResearchDocument[]>([])
  const [changelog, setChangelog] = useState<ResearchChangeEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hideReference, setHideReference] = useState(false)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(initialSource)
  const [selectedFieldPath, setSelectedFieldPath] = useState<string | null>(initialField)
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null)
  const [actor, setActor] = useState("anonymous")
  const [draftValue, setDraftValue] = useState("")
  const [draftState, setDraftState] = useState<ReviewState>("pending")
  const [draftNote, setDraftNote] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [bundle, log] = await Promise.all([
        getAnnotatedPack(dataset, cluster),
        listResearchChangelog(dataset, cluster),
      ])
      setPack(bundle.pack)
      setDocuments(bundle.documents)
      setChangelog(log.entries)
      setActiveDocumentId((current) => current || bundle.documents[0]?.document_id || null)
    } catch (err) {
      setError(describeApiError(err, "无法加载研究包"))
    } finally {
      setLoading(false)
    }
  }, [dataset, cluster])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(ACTOR_KEY)
      if (stored) setActor(stored)
    } catch {
      /* ignore */
    }
  }, [])

  const displayPack = useMemo(() => {
    if (!pack) return null
    return hideReference ? (stripReference(pack) as ResearchPack) : pack
  }, [pack, hideReference])

  const fields = useMemo(() => (displayPack ? collectFields(displayPack) : []), [displayPack])
  const anchors = displayPack?.source_anchors ?? []
  const identity = displayPack ? packIdentity(displayPack) : null
  const selectedField = fields.find((field) => field.field_path === selectedFieldPath) ?? null

  useEffect(() => {
    if (!selectedField) return
    setDraftValue(selectedField.text)
    setDraftState(selectedField.review_state)
    setDraftNote("")
  }, [selectedField?.field_path, selectedField?.text, selectedField?.review_state])

  const writeQuery = useCallback(
    (sourceId: string | null, fieldPath: string | null) => {
      const params = new URLSearchParams()
      if (sourceId) params.set("source", sourceId)
      if (fieldPath) params.set("field", fieldPath)
      const query = params.toString()
      router.replace(query ? `?${query}` : "?", { scroll: false })
    },
    [router],
  )

  const jumpToSource = useCallback(
    (sourceId: string, fieldPath?: string | null) => {
      const documentId = documentForSource(anchors, sourceId)
      if (documentId) setActiveDocumentId(documentId)
      setSelectedSourceId(sourceId)
      if (fieldPath) setSelectedFieldPath(fieldPath)
      writeQuery(sourceId, fieldPath ?? selectedFieldPath)
      window.setTimeout(() => scrollToSourceId(sourceId), 50)
    },
    [anchors, selectedFieldPath, writeQuery],
  )

  const selectField = useCallback(
    (field: AnnotField, sourceId?: string) => {
      const nextSource = sourceId || field.source_ids[0] || null
      setSelectedFieldPath(field.field_path)
      if (nextSource) {
        jumpToSource(nextSource, field.field_path)
      } else {
        setSelectedSourceId(null)
        writeQuery(null, field.field_path)
      }
    },
    [jumpToSource, writeQuery],
  )

  const persistActor = (name: string) => {
    setActor(name)
    try {
      window.sessionStorage.setItem(ACTOR_KEY, name)
    } catch {
      /* ignore */
    }
  }

  const saveField = async () => {
    if (!selectedField) return
    setSaving(true)
    setError(null)
    try {
      const result = await patchResearchField(dataset, cluster, {
        field_path: selectedField.field_path,
        actor,
        note: draftNote,
        value: draftValue,
        review_state: draftState,
      })
      setPack(result.pack)
      setDocuments(result.documents)
      setChangelog((current) => [result.change, ...current])
      setDraftNote("")
    } catch (err) {
      setError(describeApiError(err, "保存失败"))
    } finally {
      setSaving(false)
    }
  }

  const savePackReview = async (state: ReviewState) => {
    setSaving(true)
    setError(null)
    try {
      const result = await patchResearchReview(dataset, cluster, {
        review_state: state,
        actor,
        note: draftNote,
      })
      setPack(result.pack)
      setChangelog((current) => [result.change, ...current])
    } catch (err) {
      setError(describeApiError(err, "更新复核状态失败"))
    } finally {
      setSaving(false)
    }
  }

  const activeDocument = documents.find((doc) => doc.document_id === activeDocumentId) || documents[0]
  const activeAnchors = anchors.filter((anchor) => anchor.document_id === activeDocument?.document_id)

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        正在载入研究包
      </div>
    )
  }

  if (!displayPack || !identity) {
    return (
      <div className="px-4 py-6">
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error || "未找到研究包"}</AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="mt-4">
          <Link href="/research">返回列表</Link>
        </Button>
      </div>
    )
  }

  const grouped = COLUMN_ORDER.map((column) => ({
    id: column,
    label: COLUMN_LABELS[column],
    items: fields.filter((field) => field.group === column),
  })).filter((group) => group.items.length > 0)
  const extraGroups = ["task_labels"].map((id) => ({
    id,
    label: fields.find((field) => field.group === id)?.groupLabel || id,
    items: fields.filter((field) => field.group === id),
  })).filter((group) => group.items.length > 0)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href="/research">
              <ArrowLeft className="size-4" />
              研究包
            </Link>
          </Button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[17px] font-medium tracking-tight">
              {displayPack.caption.case_name || cluster}
            </h1>
            <p className="mt-0.5 font-mono text-[12px] text-muted-foreground">
              {DATASET_LABELS[identity.dataset_id]} / {identity.cluster_id} / {identity.pack_version} ·{" "}
              {TASK_TYPE_LABELS[identity.task_type]}
            </p>
          </div>
          <ReviewBadge state={displayPack.review_state} />
          <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
            <input
              type="checkbox"
              checked={hideReference}
              onChange={(event) => setHideReference(event.target.checked)}
            />
            角色视图（隐藏参照）
          </label>
        </div>
        {error ? (
          <Alert variant="destructive" className="mt-3">
            <AlertCircle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,1fr)_260px]">
        <section className="flex min-h-0 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
            <h2 className="text-[13px] font-medium">原文</h2>
            <p className="text-[11px] text-muted-foreground">点击字段跳到 source_id</p>
          </div>
          <div className="flex gap-1 overflow-x-auto px-3 py-2">
            {documents.map((doc) => (
              <button
                key={doc.document_id}
                type="button"
                onClick={() => setActiveDocumentId(doc.document_id)}
                className={cn(
                  "rounded-md px-2 py-1 text-[12px]",
                  doc.document_id === activeDocument?.document_id
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary",
                )}
              >
                {doc.document_id} {doc.title ? `· ${doc.title}` : ""}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
            {activeDocument ? (
              <SourceDocument
                text={activeDocument.text}
                anchors={activeAnchors}
                selectedSourceId={selectedSourceId}
                onSelectSource={(sourceId) => jumpToSource(sourceId, selectedFieldPath)}
              />
            ) : (
              <p className="text-sm text-muted-foreground">没有原文</p>
            )}
          </div>
        </section>

        <section className="flex min-h-0 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className="border-b border-border px-3 py-2">
            <h2 className="text-[13px] font-medium">提取</h2>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <div className="space-y-2">
              {anchors.map((anchor) => {
                const active = anchor.source_id === selectedSourceId
                return (
                  <button
                    key={anchor.source_id}
                    type="button"
                    onClick={() => jumpToSource(anchor.source_id, selectedFieldPath)}
                    className={cn(
                      "w-full rounded-md border px-3 py-2 text-left",
                      active ? "border-primary bg-primary/5" : "border-border hover:bg-secondary",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px]">{anchor.source_id}</span>
                      <ReviewBadge state={anchor.review_state} />
                    </div>
                    <p className="mt-1 text-[13px] leading-5">{anchor.quote || "（无摘录）"}</p>
                  </button>
                )
              })}
            </div>
          </div>
        </section>

        <section className="flex min-h-0 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className="border-b border-border px-3 py-2">
            <h2 className="text-[13px] font-medium">标注字段</h2>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {[...grouped, ...extraGroups].map((group) => (
              <div key={group.id} className="mb-4">
                <h3 className="mb-2 text-[12px] font-medium text-muted-foreground">{group.label}</h3>
                <div className="space-y-2">
                  {group.items.map((field) => {
                    const active = field.field_path === selectedFieldPath
                    return (
                      <article
                        key={field.field_path}
                        className={cn(
                          "rounded-md border px-3 py-2",
                          active ? "border-primary bg-primary/5" : "border-border",
                        )}
                      >
                        <button type="button" className="w-full text-left" onClick={() => selectField(field)}>
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className="text-[13px] font-medium">{field.title}</p>
                              <p className="font-mono text-[11px] text-muted-foreground">{field.item_id}</p>
                            </div>
                            <ReviewBadge state={field.review_state} />
                          </div>
                          <p className="mt-1 text-[13px] leading-5">{field.text || "—"}</p>
                        </button>
                        {field.source_ids.length ? (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {field.source_ids.map((sourceId) => (
                              <button
                                key={sourceId}
                                type="button"
                                onClick={() => selectField(field, sourceId)}
                                className={cn(
                                  "rounded-full border px-2 py-0.5 font-mono text-[11px]",
                                  sourceId === selectedSourceId
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border text-muted-foreground hover:bg-secondary",
                                )}
                              >
                                {sourceId}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-2 text-[11px] text-muted-foreground">无 source_id</p>
                        )}
                        {active ? (
                          <div className="mt-3 space-y-2 border-t border-border pt-3">
                            <Label htmlFor="field-value">字段值</Label>
                            <Textarea
                              id="field-value"
                              value={draftValue}
                              onChange={(event) => setDraftValue(event.target.value)}
                              rows={3}
                            />
                            <div className="flex flex-wrap items-center gap-2">
                              <Select value={draftState} onValueChange={(value) => setDraftState(value as ReviewState)}>
                                <SelectTrigger size="sm">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {REVIEW_STATES.map((state) => (
                                    <SelectItem key={state} value={state}>
                                      {REVIEW_STATE_LABELS[state]}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <Input
                                value={draftNote}
                                onChange={(event) => setDraftNote(event.target.value)}
                                placeholder="修改说明"
                                className="h-8 min-w-[140px] flex-1"
                              />
                              <Button type="button" size="sm" onClick={() => void saveField()} disabled={saving}>
                                {saving ? "保存中" : "保存覆盖层"}
                              </Button>
                            </div>
                            <p className="text-[11px] text-muted-foreground">
                              写入 SQLite 覆盖层，不改 pack.json。
                            </p>
                          </div>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              </div>
            ))}
            {!hideReference && displayPack.reference ? (
              <div className="rounded-md border border-dashed border-border px-3 py-2">
                <h3 className="text-[12px] font-medium text-muted-foreground">参照层（评价者可见）</h3>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  版本 {displayPack.reference.reference_version}。角色视图必须删除 reference。
                </p>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="flex min-h-0 flex-col">
          <div className="border-b border-border px-3 py-2">
            <h2 className="text-[13px] font-medium">修改记录</h2>
          </div>
          <div className="space-y-3 overflow-y-auto p-3">
            <div>
              <Label htmlFor="actor">复核人</Label>
              <Input
                id="actor"
                value={actor}
                onChange={(event) => persistActor(event.target.value)}
                className="mt-1 h-8"
              />
            </div>
            <div>
              <Label>整包复核</Label>
              <Select
                value={asReview(displayPack.review_state)}
                onValueChange={(value) => void savePackReview(value as ReviewState)}
              >
                <SelectTrigger className="mt-1 w-full" size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REVIEW_STATES.map((state) => (
                    <SelectItem key={state} value={state}>
                      {REVIEW_STATE_LABELS[state]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {changelog.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">还没有覆盖层修改。</p>
            ) : (
              <ol className="space-y-2">
                {changelog.map((entry) => (
                  <li key={entry.id} className="rounded-md border border-border px-2 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] font-medium">{entry.actor}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">{entry.created_at}</span>
                    </div>
                    <button
                      type="button"
                      className="mt-1 text-left font-mono text-[11px] text-primary"
                      onClick={() => {
                        const field = fields.find((item) => item.field_path === entry.field_path)
                        if (field) selectField(field)
                        else {
                          setSelectedFieldPath(entry.field_path)
                          writeQuery(selectedSourceId, entry.field_path)
                        }
                      }}
                    >
                      {entry.field_path}
                    </button>
                    <p className="mt-1 text-[12px] text-muted-foreground">
                      {formatChangeValue(entry.from_value)} → {formatChangeValue(entry.to_value)}
                    </p>
                    {entry.review_state ? <ReviewBadge state={entry.review_state} className="mt-1" /> : null}
                    {entry.note ? <p className="mt-1 text-[12px]">{entry.note}</p> : null}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
