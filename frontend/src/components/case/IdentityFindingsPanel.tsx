import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  ArrowLeftIcon,
  CheckCircle2Icon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Columns2Icon,
  GaugeIcon,
  InfoIcon,
  LayersIcon,
  Loader2Icon,
  MapPinOffIcon,
  MessageSquareIcon,
  RotateCcwIcon,
} from "lucide-react"

import { reviewFinding } from "@/api/cases"
import { Button } from "@/components/ui/button"
import { PdfOverlayViewer, type OverlayColor } from "@/components/case/PdfOverlayViewer"
import {
  DOCUMENT_TYPE_LABELS,
  IDENTITY_FIELD_LABELS,
  type CaseDetail,
  type CaseDetailDocument,
  type CrossDocumentFinding,
  type FindingCounts,
  type FindingSeverity,
  type I18nCatalog,
} from "@/types/case"
import { cn } from "@/lib/utils"

interface IdentityFindingsPanelProps {
  findings: CrossDocumentFinding[]
  documents: CaseDetailDocument[]
  isProcessing?: boolean
  caseId?: string
  canAct?: boolean
  caseStatus?: string
  findingCounts?: FindingCounts
  catalog?: I18nCatalog | null
  currentLang?: string
  token?: string | null
}

const SEVERITY_CONFIG: Record<
  FindingSeverity,
  {
    label: string
    badgeClass: string
    icon: React.ComponentType<{ className?: string }>
    overlayColor: OverlayColor
  }
> = {
  critical: {
    label: "Must be corrected",
    badgeClass: "bg-red-600 text-white font-semibold shadow-xs",
    icon: AlertCircleIcon,
    overlayColor: "critical",
  },
  high: {
    label: "Serious mismatch",
    badgeClass: "border-2 border-red-600 text-red-700 bg-red-50 font-semibold",
    icon: AlertTriangleIcon,
    overlayColor: "critical",
  },
  medium: {
    label: "Please check",
    badgeClass: "border border-amber-300 bg-amber-50 text-amber-800 font-medium",
    icon: AlertTriangleIcon,
    overlayColor: "warning",
  },
  low: {
    label: "Minor difference",
    badgeClass: "border border-yellow-200 bg-yellow-50/80 text-yellow-800 font-normal",
    icon: InfoIcon,
    overlayColor: "warning",
  },
  info: {
    label: "No problem",
    badgeClass: "border border-emerald-200 bg-emerald-50 text-emerald-800 font-medium",
    icon: CheckCircle2Icon,
    overlayColor: "neutral",
  },
}

const SEVERITY_ORDER: Record<FindingSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
}

export function getFindingSeverityScore(finding: { severity: FindingSeverity; field_name?: string; severity_score?: number }): number {
  if (typeof finding.severity_score === "number" && finding.severity_score > 0) {
    return finding.severity_score
  }
  switch (finding.severity) {
    case "critical":
      return finding.field_name === "full_name" || finding.field_name === "photo" ? 95 : 90
    case "high":
      return finding.field_name === "date_of_birth" || finding.field_name === "gender" ? 75 : 70
    case "medium":
      return 50
    case "low":
      return 25
    case "info":
    default:
      return 0
  }
}

export function getSeverityScoreConfig(score: number) {
  if (score >= 80) {
    return {
      tier: "critical",
      label: "Critical",
      badgeClass: "bg-red-50 text-red-700 border-red-300 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800",
      barClass: "bg-red-600",
      textClass: "text-red-700",
    }
  }
  if (score >= 60) {
    return {
      tier: "high",
      label: "High",
      badgeClass: "bg-orange-50 text-orange-700 border-orange-300 dark:bg-orange-950/40 dark:text-orange-300 dark:border-orange-800",
      barClass: "bg-orange-500",
      textClass: "text-orange-700",
    }
  }
  if (score >= 40) {
    return {
      tier: "medium",
      label: "Medium",
      badgeClass: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
      barClass: "bg-amber-500",
      textClass: "text-amber-700",
    }
  }
  if (score >= 15) {
    return {
      tier: "low",
      label: "Low",
      badgeClass: "bg-blue-50 text-blue-700 border-blue-300 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
      barClass: "bg-blue-500",
      textClass: "text-blue-700",
    }
  }
  return {
    tier: "info",
    label: "Safe",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    barClass: "bg-emerald-500",
    textClass: "text-emerald-700",
  }
}

export function SeverityScoreBadge({
  score,
  label = "Severity score",
  className,
}: {
  score: number
  label?: string
  className?: string
}) {
  const config = getSeverityScoreConfig(score)
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border shadow-2xs shrink-0 transition-all",
        config.badgeClass,
        className
      )}
      title={`${label}: ${score}/100 (${config.label})`}
    >
      <GaugeIcon className="size-3 shrink-0" />
      <span className="text-[10px] uppercase font-bold tracking-wider opacity-80">{label}:</span>
      <span className="font-mono font-extrabold text-xs">{score}</span>
      <span className="text-[10px] opacity-60 font-mono">/100</span>
      <span className="w-8 sm:w-10 h-1.5 rounded-full bg-black/10 dark:bg-white/20 overflow-hidden inline-flex ml-0.5">
        <span
          className={cn("h-full rounded-full transition-all duration-300", config.barClass)}
          style={{ width: `${Math.max(score === 0 ? 0 : 8, score)}%` }}
        />
      </span>
    </span>
  )
}

function formatReviewDate(iso: string | null | undefined): string {
  if (!iso) return ""
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
  } catch {
    return iso
  }
}

/**
 * Word-level difference highlighter: tokens that don't appear in otherValue are highlighted in bold.
 */
function HighlightDiffWords({
  value,
  otherValue,
}: {
  value: string | null | undefined
  otherValue: string | null | undefined
}) {
  if (!value) {
    return <span className="italic text-muted-foreground">Not on document</span>
  }
  if (!otherValue) {
    return <span className="font-semibold text-foreground">{value}</span>
  }

  // Tokenize otherValue into clean words
  const otherWords = new Set(
    otherValue
      .toLowerCase()
      .split(/[\s,.-]+/)
      .filter(Boolean)
  )

  const tokens = value.split(/(\s+|[,.-]+)/)

  return (
    <span className="text-sm leading-snug">
      {tokens.map((token, i) => {
        const clean = token.toLowerCase().trim()
        const isWord = clean.length > 0 && !/^[\s,.-]+$/.test(clean)
        const isDiff = isWord && !otherWords.has(clean)

        return (
          <span
            key={i}
            className={cn(
              isDiff ? "font-bold text-foreground underline decoration-primary/40 underline-offset-2" : "text-muted-foreground/90"
            )}
          >
            {token}
          </span>
        )
      })}
    </span>
  )
}

export function IdentityFindingsPanel({
  findings,
  documents,
  isProcessing = false,
  caseId,
  canAct = false,
  caseStatus,
  findingCounts,
  catalog,
  currentLang = "en",
  token,
}: IdentityFindingsPanelProps) {
  const [activeTab, setActiveTab] = React.useState<"conflicts" | "harmless">("conflicts")
  const [expandedFields, setExpandedFields] = React.useState<Record<string, boolean>>({})
  const [compareFindingId, setCompareFindingId] = React.useState<string | null>(null)
  const [actionError, setActionError] = React.useState<{ findingId: string; message: string } | null>(null)

  const queryClient = useQueryClient()

  // Review permission: can_act is true and case is NOT decided (approved/rejected/closed)
  const isCaseDecided = caseStatus === "approved" || caseStatus === "rejected" || caseStatus === "closed"
  const canReview = Boolean(canAct && !isCaseDecided && token && caseId)

  // TanStack Query mutation to review finding (accept / dismiss / pending)
  const reviewMutation = useMutation({
    mutationFn: async ({
      findingId,
      decision,
      note,
    }: {
      findingId: string
      decision: "accepted" | "dismissed" | "pending"
      note?: string | null
    }) => {
      if (!caseId || !token) throw new Error("Missing caseId or token")
      setActionError(null)
      return reviewFinding(caseId, findingId, { decision, note }, currentLang, token)
    },
    onSuccess: (data) => {
      // Update local query cache for instant reactivity
      queryClient.setQueryData(["case", caseId, token, currentLang], (old: CaseDetail | undefined) => {
        if (!old) return old
        return {
          ...old,
          cross_document_findings: old.cross_document_findings.map((f) =>
            f.id === data.finding.id ? data.finding : f
          ),
          finding_counts: data.finding_counts,
        }
      })
      queryClient.invalidateQueries({ queryKey: ["case", caseId] })
      queryClient.invalidateQueries({ queryKey: ["caseProfile", caseId] })
      queryClient.invalidateQueries({ queryKey: ["prefilledForm", caseId] })
      queryClient.invalidateQueries({ queryKey: ["formsList"] })
    },
    onError: (err: Error, variables) => {
      setActionError({
        findingId: variables.findingId,
        message: err.message || "Could not save review decision",
      })
    },
  })

  const compareFinding = React.useMemo(() => {
    return compareFindingId ? findings.find((f) => f.id === compareFindingId) ?? null : null
  }, [findings, compareFindingId])

  const conflicts = React.useMemo(() => {
    return findings
      .filter((f) => f.classification === "conflict")
      .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  }, [findings])

  const harmless = React.useMemo(() => {
    return findings.filter((f) => f.classification === "harmless_variant")
  }, [findings])

  // Group findings by field_name
  const groupFindings = (items: CrossDocumentFinding[]) => {
    const groups: Record<string, CrossDocumentFinding[]> = {}
    items.forEach((item) => {
      const key = item.field_name || "other"
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
    })
    return groups
  }

  const conflictGroups = React.useMemo(() => groupFindings(conflicts), [conflicts])
  const harmlessGroups = React.useMemo(() => groupFindings(harmless), [harmless])

  const toggleGroup = (key: string) => {
    setExpandedFields((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const isGroupExpanded = (key: string, isConflictTab: boolean) => {
    if (expandedFields[key] !== undefined) return expandedFields[key]
    return isConflictTab
  }

  // Count calculations
  const openCount =
    findingCounts?.open ??
    conflicts.filter((f) => !f.review_status || f.review_status === "pending").length

  const confirmedCount =
    findingCounts?.conflict_confirmed ??
    findings.filter((f) => f.resolution === "conflict_confirmed").length

  const noIssueCount =
    findingCounts?.no_issue ??
    conflicts.filter((f) => f.resolution === "no_issue").length

  const harmlessCount =
    findingCounts?.ignored_as_harmless ??
    harmless.filter((f) => f.resolution !== "conflict_confirmed").length

  const maxConflictScore = React.useMemo(() => {
    if (conflicts.length === 0) return 0
    return Math.max(...conflicts.map((f) => getFindingSeverityScore(f)))
  }, [conflicts])

  // Find next / previous finding in side-by-side view
  const currentFindingList = activeTab === "conflicts" ? conflicts : harmless
  const currentIndex = compareFinding ? currentFindingList.findIndex((f) => f.id === compareFinding.id) : -1

  const goNextFinding = () => {
    if (currentIndex >= 0 && currentIndex < currentFindingList.length - 1) {
      setCompareFindingId(currentFindingList[currentIndex + 1].id)
    }
  }

  const goPrevFinding = () => {
    if (currentIndex > 0) {
      setCompareFindingId(currentFindingList[currentIndex - 1].id)
    }
  }

  return (
    <div id="findings-panel" className="flex flex-col gap-4 font-sans">
      {/* ================= SUMMARY BANNER ================= */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            {isProcessing ? (
              <>
                <Loader2Icon className="size-4.5 text-primary animate-spin" />
                <div>
                  <span className="text-sm font-semibold text-foreground">Checking the documents…</span>
                  <p className="text-xs text-muted-foreground mt-0.5">Automated cross-document verification in progress</p>
                </div>
              </>
            ) : conflicts.length === 0 && harmless.length === 0 ? (
              <>
                <div className="size-7 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                  <CheckCircle2Icon className="size-4.5" />
                </div>
                <div>
                  <span className="text-sm font-bold text-emerald-900">All documents agree</span>
                  <p className="text-xs text-emerald-700 mt-0.5">No contradictions or name/DOB discrepancies were detected across evidence.</p>
                </div>
              </>
            ) : (
              <div>
                <div className="flex items-center gap-2 text-sm font-bold text-foreground flex-wrap">
                  <LayersIcon className="size-4 text-primary shrink-0" />
                  <span>
                    {openCount > 0 ? (
                      <span className="text-destructive">
                        {openCount} open conflict{openCount === 1 ? "" : "s"} need attention
                      </span>
                    ) : confirmedCount > 0 ? (
                      <span className="text-red-700 font-bold">
                        {confirmedCount} confirmed conflict{confirmedCount === 1 ? "" : "s"}
                      </span>
                    ) : (
                      <span className="text-emerald-700 font-bold">No open conflicts</span>
                    )}
                    {confirmedCount > 0 && openCount > 0 && (
                      <span className="text-red-700 font-semibold text-xs ml-1.5">
                        ({confirmedCount} confirmed)
                      </span>
                    )}
                    {noIssueCount > 0 && (
                      <span className="text-emerald-700 font-medium text-xs ml-1.5">
                        · {noIssueCount} dismissed
                      </span>
                    )}
                    {" · "}
                    <span className="text-muted-foreground font-medium text-xs">
                      {harmlessCount} difference{harmlessCount === 1 ? "" : "s"} ignored as harmless
                    </span>
                  </span>
                  {maxConflictScore > 0 && (
                    <SeverityScoreBadge score={maxConflictScore} label="Max score" className="ml-1.5" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Cross-checked names, dates of birth, addresses, income, and identity numbers.
                </p>
              </div>
            )}
          </div>

          {!isProcessing && (conflicts.length > 0 || harmless.length > 0) && (
            <div className="flex items-center gap-1.5 p-1 bg-muted/60 rounded-lg text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveTab("conflicts")}
                className={cn(
                  "px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5",
                  activeTab === "conflicts"
                    ? "bg-card text-foreground shadow-2xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <span>Needs attention</span>
                <span
                  className={cn(
                    "px-1.5 py-0.2 rounded-full text-[10px]",
                    openCount > 0
                      ? "bg-red-100 text-red-700 font-bold"
                      : conflicts.length > 0
                      ? "bg-emerald-100 text-emerald-800 font-semibold"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {openCount > 0 ? openCount : conflicts.length}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("harmless")}
                className={cn(
                  "px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5",
                  activeTab === "harmless"
                    ? "bg-card text-foreground shadow-2xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <span>Ignored as harmless</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-muted text-muted-foreground font-medium">
                  {harmless.length}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ================= HARMLESS HELPER HEADER ================= */}
      {activeTab === "harmless" && harmless.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-2.5 text-xs text-slate-700 flex items-center justify-between">
          <span className="font-semibold">Differences we ignored ({harmless.length})</span>
          <span className="text-slate-500 text-[11px]">These are the same details written in a different way.</span>
        </div>
      )}

      {/* ================= FINDINGS LIST ================= */}
      {!isProcessing && (
        <div className="flex flex-col gap-3">
          {activeTab === "conflicts" && conflicts.length === 0 && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-6 text-center text-xs text-emerald-800">
              <CheckCircle2Icon className="size-6 text-emerald-600 mx-auto mb-2" />
              <p className="font-semibold text-sm">No conflicts detected</p>
              <p className="text-muted-foreground mt-1">All extracted person details match across submitted documents.</p>
            </div>
          )}

          {activeTab === "harmless" && harmless.length === 0 && (
            <div className="rounded-xl border border-border bg-card p-6 text-center text-xs text-muted-foreground">
              No harmless spelling or abbreviation differences found.
            </div>
          )}

          {Object.entries(activeTab === "conflicts" ? conflictGroups : harmlessGroups).map(([fieldName, items]) => {
            const fieldLabel = catalog?.fields?.[fieldName] ?? IDENTITY_FIELD_LABELS[fieldName] ?? fieldName
            const isExpanded = isGroupExpanded(fieldName, activeTab === "conflicts")
            const groupMaxScore = Math.max(...items.map((it) => getFindingSeverityScore(it)))

            return (
              <div key={fieldName} className="rounded-xl border border-border bg-card shadow-2xs overflow-hidden">
                {/* Group Header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(fieldName)}
                  className="w-full flex items-center justify-between p-3.5 bg-muted/20 hover:bg-muted/40 transition-colors text-left"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    {isExpanded ? (
                      <ChevronDownIcon className="size-4 text-muted-foreground" />
                    ) : (
                      <ChevronRightIcon className="size-4 text-muted-foreground" />
                    )}
                    <span className="text-sm font-bold text-foreground">{fieldLabel}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
                      {items.length} {items.length === 1 ? "item" : "items"}
                    </span>
                    {groupMaxScore > 0 && (
                      <SeverityScoreBadge score={groupMaxScore} className="ml-1" />
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground">
                    {isExpanded ? "Collapse" : "Expand"}
                  </span>
                </button>

                {/* Group Items */}
                {isExpanded && (
                  <div className="divide-y divide-border/60 p-3 flex flex-col gap-3">
                    {items.map((finding) => (
                      <FindingCard
                        key={finding.id}
                        finding={finding}
                        catalog={catalog}
                        canReview={canReview}
                        isCaseDecided={isCaseDecided}
                        caseStatus={caseStatus}
                        isReviewing={reviewMutation.isPending && reviewMutation.variables?.findingId === finding.id}
                        reviewError={actionError?.findingId === finding.id ? actionError.message : null}
                        onReview={(decision, note) =>
                          reviewMutation.mutate({ findingId: finding.id, decision, note })
                        }
                        onShowOnDocuments={() => setCompareFindingId(finding.id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* ================= SIDE-BY-SIDE COMPARE MODAL ================= */}
      {compareFinding && (
        <SideBySideCompareModal
          finding={compareFinding}
          documents={documents}
          catalog={catalog}
          canReview={canReview}
          isCaseDecided={isCaseDecided}
          caseStatus={caseStatus}
          isReviewing={reviewMutation.isPending && reviewMutation.variables?.findingId === compareFinding.id}
          reviewError={actionError?.findingId === compareFinding.id ? actionError.message : null}
          onReview={(decision, note) =>
            reviewMutation.mutate({ findingId: compareFinding.id, decision, note })
          }
          currentIndex={currentIndex}
          totalCount={currentFindingList.length}
          onClose={() => setCompareFindingId(null)}
          onNext={currentIndex < currentFindingList.length - 1 ? goNextFinding : undefined}
          onPrev={currentIndex > 0 ? goPrevFinding : undefined}
        />
      )}
    </div>
  )
}

/**
 * Finding Card component rendering side-by-side values, severity chip, structured message, and review controls.
 */
function FindingCard({
  finding,
  catalog,
  canReview,
  isCaseDecided,
  caseStatus,
  isReviewing,
  reviewError,
  onReview,
  onShowOnDocuments,
}: {
  finding: CrossDocumentFinding
  catalog?: I18nCatalog | null
  canReview: boolean
  isCaseDecided: boolean
  caseStatus?: string
  isReviewing: boolean
  reviewError: string | null
  onReview: (decision: "accepted" | "dismissed" | "pending", note?: string | null) => void
  onShowOnDocuments: () => void
}) {
  const [showNoteInput, setShowNoteInput] = React.useState(false)
  const [noteText, setNoteText] = React.useState("")

  const sev = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.medium
  const SevIcon = sev.icon
  const findingScore = getFindingSeverityScore(finding)

  // Localized severity & field label via catalog
  const severityLabel = catalog?.severities?.[finding.severity] ?? finding.message?.severity_label ?? sev.label
  const fieldLabel = catalog?.fields?.[finding.field_name] ?? finding.message?.field_label ?? IDENTITY_FIELD_LABELS[finding.field_name] ?? finding.field_name

  const evA = finding.evidence?.[0]
  const evB = finding.evidence?.[1]

  const docTypeA = evA?.document_type
    ? (catalog?.documents?.[evA.document_type] ?? DOCUMENT_TYPE_LABELS[evA.document_type] ?? evA.document_type)
    : "Document 1"
  const docTypeB = evB?.document_type
    ? (catalog?.documents?.[evB.document_type] ?? DOCUMENT_TYPE_LABELS[evB.document_type] ?? evB.document_type)
    : "Document 2"

  const isSameDocType = evA?.document_type && evA.document_type === evB?.document_type

  const isReviewed = finding.review_status && finding.review_status !== "pending"
  const isConflict = finding.classification === "conflict"

  const handleDecision = (decision: "accepted" | "dismissed") => {
    onReview(decision, noteText.trim() ? noteText.trim() : null)
    setNoteText("")
    setShowNoteInput(false)
  }

  const handleUndo = () => {
    onReview("pending", null)
    setNoteText("")
    setShowNoteInput(false)
  }

  return (
    <div id={`finding-${finding.field_name}`} className="rounded-xl border border-border/80 bg-background p-4 flex flex-col gap-3.5 transition-all hover:border-border">
      {/* Card Header: Chip + Severity Score + Field Label + Resolution Chip + Show on Documents Button */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs shrink-0",
              sev.badgeClass
            )}
          >
            <SevIcon className="size-3.5" />
            {severityLabel}
          </span>
          <SeverityScoreBadge score={findingScore} />
          <span className="text-sm font-bold text-foreground">{fieldLabel}</span>

          {/* Resolution Badge if reviewed */}
          {isReviewed && (
            <span
              className={cn(
                "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold",
                finding.resolution === "conflict_confirmed"
                  ? "bg-red-100 text-red-800 border border-red-200"
                  : "bg-emerald-100 text-emerald-800 border border-emerald-200"
              )}
            >
              {finding.resolution === "conflict_confirmed" ? (
                <>
                  <AlertCircleIcon className="size-3" />
                  {isConflict ? "Conflict confirmed" : "Overruled as conflict"}
                </>
              ) : (
                <>
                  <CheckIcon className="size-3" />
                  {isConflict ? "Dismissed (No issue)" : "Accepted as harmless"}
                </>
              )}
            </span>
          )}
        </div>

        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onShowOnDocuments}
          className="h-8 gap-1.5 text-xs font-semibold rounded-lg hover:bg-primary hover:text-primary-foreground transition-colors"
        >
          <Columns2Icon className="size-3.5" />
          Show on documents
        </Button>
      </div>

      {/* Side-by-Side Values */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-lg bg-muted/20 border border-border/60">
        {/* Left Side: Document A */}
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-foreground truncate" title={evA?.document_filename}>
              {docTypeA}
            </span>
            {isSameDocType && evA?.document_filename && (
              <span className="text-[11px] text-muted-foreground truncate">({evA.document_filename})</span>
            )}
          </div>
          <div className="p-2 rounded bg-background border border-border/50">
            <HighlightDiffWords value={evA?.value} otherValue={evB?.value} />
          </div>
        </div>

        {/* Right Side: Document B */}
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-foreground truncate" title={evB?.document_filename}>
              {docTypeB}
            </span>
            {isSameDocType && evB?.document_filename && (
              <span className="text-[11px] text-muted-foreground truncate">({evB.document_filename})</span>
            )}
          </div>
          <div className="p-2 rounded bg-background border border-border/50">
            <HighlightDiffWords value={evB?.value} otherValue={evA?.value} />
          </div>
        </div>
      </div>

      {/* Multilingual Structured Message (summary, explanation, action as 3 separate lines) */}
      {finding.message ? (
        <div className="flex flex-col gap-2 text-xs rounded-lg p-3 bg-muted/25 border border-border/50">
          {finding.message.summary && (
            <p className="font-semibold text-foreground leading-snug">
              {finding.message.summary}
            </p>
          )}
          {finding.message.explanation && (
            <p className="text-muted-foreground leading-relaxed">
              {finding.message.explanation}
            </p>
          )}
          {finding.message.action && (
            <div className="flex items-start gap-1.5 text-foreground/90 bg-card border border-border/70 rounded-md px-2.5 py-1.5 text-[11px] leading-relaxed shadow-2xs">
              <span className="font-bold text-primary shrink-0">Action:</span>
              <span>{finding.message.action}</span>
            </div>
          )}
        </div>
      ) : (
        /* Invoice findings fallback (message is null on invoice findings) */
        <p className="text-xs text-muted-foreground leading-relaxed">{finding.description}</p>
      )}

      {/* Reviewer Action Slot / Review History */}
      <div className="pt-2 border-t border-dashed border-border/60 flex flex-col gap-2">
        {/* If reviewed, show reviewer details & note */}
        {isReviewed && (
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs bg-muted/30 p-2.5 rounded-lg border border-border/50">
            <div className="flex flex-col gap-0.5">
              <div className="text-[11px] text-muted-foreground">
                Reviewed by <span className="font-semibold text-foreground">{finding.reviewed_by_name || "Reviewer"}</span>
                {finding.reviewed_at && <span> on {formatReviewDate(finding.reviewed_at)}</span>}
              </div>
              {finding.review_note && (
                <p className="text-xs text-foreground italic mt-0.5 flex items-start gap-1">
                  <MessageSquareIcon className="size-3 text-muted-foreground mt-0.5 shrink-0" />
                  <span>“{finding.review_note}”</span>
                </p>
              )}
            </div>

            {canReview && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={isReviewing}
                onClick={handleUndo}
                className="h-7 text-xs font-medium text-muted-foreground hover:text-foreground gap-1"
              >
                {isReviewing ? (
                  <Loader2Icon className="size-3 animate-spin" />
                ) : (
                  <RotateCcwIcon className="size-3" />
                )}
                Undo decision
              </Button>
            )}
          </div>
        )}

        {/* If not reviewed and reviewer can act */}
        {!isReviewed && canReview && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setShowNoteInput(!showNoteInput)}
                className="text-[11px] font-medium text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              >
                <MessageSquareIcon className="size-3" />
                {showNoteInput ? "Hide note" : noteText ? "Edit note" : "+ Add reviewer note"}
              </button>

              <div className="flex items-center gap-2">
                {isConflict ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isReviewing}
                      onClick={() => handleDecision("dismissed")}
                      className="h-8 text-xs font-semibold rounded-lg hover:bg-emerald-50 hover:text-emerald-800 hover:border-emerald-300"
                    >
                      {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                      Dismiss (no issue)
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={isReviewing}
                      onClick={() => handleDecision("accepted")}
                      className="h-8 text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-700 text-white shadow-2xs"
                    >
                      {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                      Confirm conflict
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isReviewing}
                      onClick={() => handleDecision("accepted")}
                      className="h-8 text-xs font-semibold rounded-lg hover:bg-emerald-50 hover:text-emerald-800"
                    >
                      {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                      Accept harmless
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isReviewing}
                      onClick={() => handleDecision("dismissed")}
                      className="h-8 text-xs font-semibold rounded-lg text-red-700 hover:bg-red-50 hover:border-red-300"
                    >
                      {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                      Treat as conflict
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Optional Note Textarea */}
            {showNoteInput && (
              <div className="flex flex-col gap-1 mt-1 animate-in fade-in duration-150">
                <textarea
                  value={noteText}
                  maxLength={1000}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Optional rationale for this decision (max 1000 characters)..."
                  className="w-full text-xs p-2 rounded-lg border border-border bg-background focus:ring-1 focus:ring-primary focus:outline-hidden resize-none min-h-[58px]"
                />
                <div className="flex items-center justify-between text-[10px] text-muted-foreground px-1">
                  <span>Note is saved with your decision into the case audit trail</span>
                  <span>{noteText.length} / 1000</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* If pending and reviewer CANNOT act */}
        {!isReviewed && !canReview && isCaseDecided && (
          <div className="text-[11px] text-muted-foreground italic text-right">
            Findings frozen (case is {caseStatus})
          </div>
        )}

        {/* Mutation Error */}
        {reviewError && (
          <div className="p-2 rounded bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            {reviewError}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Side-by-side compare modal presenting both documents scrolled to bounding boxes with review controls.
 */
function SideBySideCompareModal({
  finding,
  documents,
  catalog,
  canReview,
  isCaseDecided,
  caseStatus,
  isReviewing,
  reviewError,
  onReview,
  currentIndex,
  totalCount,
  onClose,
  onNext,
  onPrev,
}: {
  finding: CrossDocumentFinding
  documents: CaseDetailDocument[]
  catalog?: I18nCatalog | null
  canReview: boolean
  isCaseDecided: boolean
  caseStatus?: string
  isReviewing: boolean
  reviewError: string | null
  onReview: (decision: "accepted" | "dismissed" | "pending", note?: string | null) => void
  currentIndex: number
  totalCount: number
  onClose: () => void
  onNext?: () => void
  onPrev?: () => void
}) {
  const [showNoteInput, setShowNoteInput] = React.useState(false)
  const [noteText, setNoteText] = React.useState("")

  const evA = finding.evidence?.[0]
  const evB = finding.evidence?.[1]

  const docA = documents.find((d) => d.id === evA?.document_id)
  const docB = documents.find((d) => d.id === evB?.document_id)

  const sev = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.medium
  const SevIcon = sev.icon
  const findingScore = getFindingSeverityScore(finding)

  // Localized severity, field, and document labels via catalog
  const severityLabel = catalog?.severities?.[finding.severity] ?? finding.message?.severity_label ?? sev.label
  const fieldLabel = catalog?.fields?.[finding.field_name] ?? finding.message?.field_label ?? IDENTITY_FIELD_LABELS[finding.field_name] ?? finding.field_name

  const docTypeA = evA?.document_type
    ? (catalog?.documents?.[evA.document_type] ?? DOCUMENT_TYPE_LABELS[evA.document_type] ?? evA.document_type)
    : "Document 1"
  const docTypeB = evB?.document_type
    ? (catalog?.documents?.[evB.document_type] ?? DOCUMENT_TYPE_LABELS[evB.document_type] ?? evB.document_type)
    : "Document 2"

  const overlayColor: OverlayColor = finding.classification === "harmless_variant" ? "neutral" : sev.overlayColor

  const isReviewed = finding.review_status && finding.review_status !== "pending"
  const isConflict = finding.classification === "conflict"

  const handleDecision = (decision: "accepted" | "dismissed") => {
    onReview(decision, noteText.trim() ? noteText.trim() : null)
    setNoteText("")
    setShowNoteInput(false)
  }

  const handleUndo = () => {
    onReview("pending", null)
    setNoteText("")
    setShowNoteInput(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-3 sm:p-6 animate-in fade-in duration-150">
      <div className="flex flex-col h-full max-h-[92vh] w-full max-w-[1520px] rounded-2xl bg-card border border-border shadow-2xl overflow-hidden">
        {/* Modal Top Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              className="gap-1.5 text-xs font-semibold rounded-lg"
            >
              <ArrowLeftIcon className="size-3.5" />
              Back to findings
            </Button>

            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold",
                  sev.badgeClass
                )}
              >
                <SevIcon className="size-3.5" />
                {severityLabel}
              </span>
              <SeverityScoreBadge score={findingScore} />
              <span className="text-sm font-bold text-foreground">{fieldLabel}</span>

              {isReviewed && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold",
                    finding.resolution === "conflict_confirmed"
                      ? "bg-red-100 text-red-800 border border-red-200"
                      : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                  )}
                >
                  {finding.resolution === "conflict_confirmed" ? (
                    <>
                      <AlertCircleIcon className="size-3" />
                      {isConflict ? "Conflict confirmed" : "Overruled as conflict"}
                    </>
                  ) : (
                    <>
                      <CheckIcon className="size-3" />
                      {isConflict ? "Dismissed (No issue)" : "Accepted as harmless"}
                    </>
                  )}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground mr-1">
              Finding {currentIndex + 1} of {totalCount}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!onPrev}
              onClick={onPrev}
              className="h-8 text-xs rounded-lg"
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!onNext}
              onClick={onNext}
              className="h-8 text-xs rounded-lg"
            >
              Next
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 text-xs rounded-lg text-muted-foreground hover:text-foreground"
            >
              Close
            </Button>
          </div>
        </div>

        {/* Modal Subheader: Three Lines (summary, explanation, action) */}
        <div className="px-5 py-3 border-b border-border/80 bg-background flex flex-col gap-1.5 text-xs">
          {finding.message ? (
            <>
              {finding.message.summary && (
                <p className="font-semibold text-foreground leading-snug">
                  {finding.message.summary}
                </p>
              )}
              {finding.message.explanation && (
                <p className="text-muted-foreground leading-relaxed">
                  {finding.message.explanation}
                </p>
              )}
              {finding.message.action && (
                <div className="flex items-start gap-1.5 text-foreground/90 bg-muted/40 border border-border/60 rounded-md px-2.5 py-1 text-[11px] leading-relaxed w-fit">
                  <span className="font-bold text-primary shrink-0">Action:</span>
                  <span>{finding.message.action}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-muted-foreground font-medium">{finding.description}</p>
          )}
        </div>

        {/* Modal Body: Two Side-by-Side Panes */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4 overflow-y-auto flex-1 min-h-0 bg-muted/10">
          {/* Left Pane: Document A */}
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-border/60">
              <div className="flex flex-col">
                <span className="text-xs font-bold text-foreground">{docTypeA}</span>
                <span className="text-[11px] text-muted-foreground font-mono truncate" title={evA?.document_filename}>
                  {evA?.document_filename}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[11px] font-semibold text-primary block">
                  {evA?.value || "Not found"}
                </span>
                {!evA?.bounding_box && (
                  <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                    <MapPinOffIcon className="size-2.5" /> Position not found on this document
                  </span>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              {docA ? (
                <PdfOverlayViewer
                  fileUrl={docA.file_url}
                  originalFilename={docA.original_filename}
                  overlays={[]}
                  selectedBox={evA?.bounding_box ?? null}
                  selectedBoxColor={overlayColor}
                />
              ) : (
                <div className="p-8 text-center text-xs text-muted-foreground">Document unavailable</div>
              )}
            </div>
          </div>

          {/* Right Pane: Document B */}
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-border/60">
              <div className="flex flex-col">
                <span className="text-xs font-bold text-foreground">{docTypeB}</span>
                <span className="text-[11px] text-muted-foreground font-mono truncate" title={evB?.document_filename}>
                  {evB?.document_filename}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[11px] font-semibold text-primary block">
                  {evB?.value || "Not found"}
                </span>
                {!evB?.bounding_box && (
                  <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                    <MapPinOffIcon className="size-2.5" /> Position not found on this document
                  </span>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              {docB ? (
                <PdfOverlayViewer
                  fileUrl={docB.file_url}
                  originalFilename={docB.original_filename}
                  overlays={[]}
                  selectedBox={evB?.bounding_box ?? null}
                  selectedBoxColor={overlayColor}
                />
              ) : (
                <div className="p-8 text-center text-xs text-muted-foreground">Document unavailable</div>
              )}
            </div>
          </div>
        </div>

        {/* Modal Footer: Action Controls for Phase 4 */}
        <div className="flex flex-col px-5 py-3 border-t border-border bg-muted/20 gap-2">
          {reviewError && (
            <div className="p-2 rounded bg-destructive/10 border border-destructive/20 text-xs text-destructive">
              {reviewError}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">
                Highlight outline: {finding.classification === "harmless_variant" ? "Neutral (ignored)" : severityLabel}
              </span>

              {isReviewed && (
                <span className="text-xs text-foreground font-medium">
                  Reviewed by {finding.reviewed_by_name || "Reviewer"}
                  {finding.reviewed_at && ` · ${formatReviewDate(finding.reviewed_at)}`}
                  {finding.review_note && ` · “${finding.review_note}”`}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Review Buttons if Reviewer can act */}
              {canReview && (
                <>
                  {isReviewed ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isReviewing}
                      onClick={handleUndo}
                      className="text-xs rounded-lg gap-1"
                    >
                      {isReviewing ? (
                        <Loader2Icon className="size-3 animate-spin" />
                      ) : (
                        <RotateCcwIcon className="size-3" />
                      )}
                      Undo decision
                    </Button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => setShowNoteInput(!showNoteInput)}
                        className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 flex items-center gap-1 mr-1"
                      >
                        <MessageSquareIcon className="size-3" />
                        {showNoteInput ? "Hide note" : noteText ? "Edit note" : "+ Note"}
                      </button>

                      {isConflict ? (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isReviewing}
                            onClick={() => handleDecision("dismissed")}
                            className="text-xs font-semibold rounded-lg hover:bg-emerald-50 hover:text-emerald-800"
                          >
                            {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                            Dismiss (no issue)
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            disabled={isReviewing}
                            onClick={() => handleDecision("accepted")}
                            className="text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-700 text-white"
                          >
                            {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                            Confirm conflict
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isReviewing}
                            onClick={() => handleDecision("accepted")}
                            className="text-xs font-semibold rounded-lg hover:bg-emerald-50 hover:text-emerald-800"
                          >
                            {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                            Accept harmless
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isReviewing}
                            onClick={() => handleDecision("dismissed")}
                            className="text-xs font-semibold rounded-lg text-red-700 hover:bg-red-50 hover:border-red-300"
                          >
                            {isReviewing && <Loader2Icon className="size-3 animate-spin mr-1" />}
                            Treat as conflict
                          </Button>
                        </>
                      )}
                    </>
                  )}
                </>
              )}

              {!canReview && isCaseDecided && (
                <span className="text-xs text-muted-foreground italic mr-2">
                  Findings frozen (case {caseStatus})
                </span>
              )}

              <Button type="button" variant="outline" size="sm" onClick={onClose} className="text-xs rounded-lg">
                Close compare view
              </Button>
            </div>
          </div>

          {/* Expandable note input in modal */}
          {showNoteInput && !isReviewed && canReview && (
            <div className="flex flex-col gap-1 pt-2 border-t border-border/50 animate-in fade-in duration-150">
              <textarea
                value={noteText}
                maxLength={1000}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Optional rationale for this decision (max 1000 characters)..."
                className="w-full text-xs p-2 rounded-lg border border-border bg-card focus:ring-1 focus:ring-primary focus:outline-hidden resize-none min-h-[50px]"
              />
              <div className="flex items-center justify-between text-[10px] text-muted-foreground px-1">
                <span>Note will be saved with your decision</span>
                <span>{noteText.length} / 1000</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
