import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  CheckCircle2Icon,
  CircleDashedIcon,
  GitCompareArrowsIcon,
  GlobeIcon,
  Loader2Icon,
  RefreshCwIcon,
  Undo2Icon,
  XCircleIcon,
} from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/api/client"
import { closeComparison, getComparison, refreshComparison, reviewFinding } from "@/api/family"
import { getLanguages } from "@/api/i18n"
import { Button } from "@/components/ui/button"
import { Nav } from "@/design-system/Nav"
import { useAuth } from "@/hooks/useAuth"
import type { ComparisonCheck, FamilyComparison } from "@/types/family"

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-900 border-red-300",
  high: "bg-red-50 text-red-800 border-red-200",
  medium: "bg-amber-50 text-amber-900 border-amber-200",
  low: "bg-yellow-50 text-yellow-900 border-yellow-200",
  info: "bg-slate-50 text-slate-700 border-slate-200",
}

const RESULT_LABEL: Record<string, string> = {
  match: "Matches",
  conflict: "Conflict",
  not_checked: "Not checked",
}

function CheckRow({
  check,
  canReview,
  busy,
  onDecide,
}: {
  check: ComparisonCheck
  canReview: boolean
  busy: boolean
  onDecide: (check: ComparisonCheck, decision: "accepted" | "dismissed" | "pending", note: string) => void
}) {
  const [note, setNote] = React.useState("")
  const isConflict = check.result === "conflict"
  const decided = check.review_status === "accepted" || check.review_status === "dismissed"

  return (
    <li
      className={`rounded-lg border p-3 text-xs flex flex-col gap-2 ${
        isConflict && !decided ? "border-red-200 bg-red-50/40" : "border-border/70 bg-background"
      }`}
    >
      <div className="flex items-start gap-2.5">
        {check.result === "match" ? (
          <CheckCircle2Icon className="size-4 text-emerald-600 shrink-0 mt-0.5" aria-label={RESULT_LABEL.match} />
        ) : isConflict ? (
          <AlertTriangleIcon className="size-4 text-red-600 shrink-0 mt-0.5" aria-label={RESULT_LABEL.conflict} />
        ) : (
          <CircleDashedIcon className="size-4 text-slate-400 shrink-0 mt-0.5" aria-label={RESULT_LABEL.not_checked} />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-foreground">{check.label}</span>
            {isConflict && (
              <span
                className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                  SEVERITY_STYLES[check.severity] ?? SEVERITY_STYLES.info
                }`}
              >
                {check.severity}
              </span>
            )}
            {check.resolution === "no_issue" && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Dismissed
              </span>
            )}
            {check.resolution === "conflict_confirmed" && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-900 border border-red-300">
                Conflict confirmed
              </span>
            )}
          </div>
          <p className="text-foreground/90 mt-0.5 leading-relaxed">{check.summary}</p>
        </div>
      </div>

      {isConflict && check.finding_id && (
        <div className="pl-6.5 flex flex-col gap-2">
          {decided ? (
            <div className="flex items-center justify-between gap-2 flex-wrap rounded-md bg-muted/40 border border-border/60 px-2.5 py-1.5">
              <span className="text-[11px] text-muted-foreground">
                {check.review_status === "accepted" ? "Confirmed" : "Dismissed"}
                {check.reviewed_by_name ? ` by ${check.reviewed_by_name}` : ""}
                {check.review_note ? ` — “${check.review_note}”` : ""}
              </span>
              {canReview && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => onDecide(check, "pending", "")}
                  className="h-6 px-2 text-[11px] gap-1"
                >
                  <Undo2Icon className="size-3" />
                  Undo
                </Button>
              )}
            </div>
          ) : (
            canReview && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor={`note-${check.finding_id}`} className="text-[11px] font-semibold text-muted-foreground">
                  Note (optional)
                </label>
                <input
                  id={`note-${check.finding_id}`}
                  type="text"
                  maxLength={1000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. Typing mistake in the form"
                  className="px-2.5 py-1.5 rounded-lg border border-border bg-background text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary"
                />
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={busy}
                    onClick={() => onDecide(check, "accepted", note)}
                    className="h-7 text-[11px] font-semibold gap-1"
                  >
                    <XCircleIcon className="size-3" />
                    Confirm conflict
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => onDecide(check, "dismissed", note)}
                    className="h-7 text-[11px] font-semibold gap-1"
                  >
                    <CheckCircle2Icon className="size-3" />
                    Dismiss
                  </Button>
                </div>
              </div>
            )
          )}
        </div>
      )}
    </li>
  )
}

export function FamilyComparisonPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const { token } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [error, setError] = React.useState<string | null>(null)

  const [lang, setLang] = React.useState<string>(() => {
    try {
      return localStorage.getItem("docsure_lang") || "en"
    } catch {
      return "en"
    }
  })
  const { data: languages = [] } = useQuery({
    queryKey: ["i18nLanguages"],
    queryFn: () => getLanguages(),
    staleTime: 5 * 60 * 1000,
  })
  const availableLanguages = React.useMemo(() => languages.filter((l) => l.available), [languages])

  const queryKey = ["familyComparison", caseId, lang, token]
  const { data, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () => getComparison(caseId as string, lang, token as string),
    enabled: Boolean(token && caseId),
  })

  const showError = (err: unknown) => setError(err instanceof ApiError ? err.message : "Something went wrong.")
  const store = (next: FamilyComparison) => {
    setError(null)
    queryClient.setQueryData(queryKey, next)
    void queryClient.invalidateQueries({ queryKey: ["familyComparisons"] })
  }

  const refresh = useMutation({
    mutationFn: () => refreshComparison(caseId as string, lang, token as string),
    onSuccess: store,
    onError: showError,
  })
  const close = useMutation({
    mutationFn: () => closeComparison(caseId as string, token as string),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["familyComparisons"] })
      navigate("/family", { replace: true })
    },
    onError: showError,
  })
  const decide = useMutation({
    mutationFn: (v: { check: ComparisonCheck; decision: "accepted" | "dismissed" | "pending"; note: string }) =>
      reviewFinding(caseId as string, v.check.finding_id as string, v.decision, v.note, token as string),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ["familyComparison", caseId] })
      void queryClient.invalidateQueries({ queryKey: ["familyComparisons"] })
    },
    onError: showError,
  })

  const shell = (children: React.ReactNode) => (
    <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900 antialiased">
      <Nav active="family" />
      {children}
    </div>
  )

  if (isLoading) {
    return shell(
      <main className="max-w-2xl w-full mx-auto px-6 py-20 text-center flex flex-col items-center gap-3">
        <Loader2Icon className="size-8 text-primary animate-spin" />
        <p className="text-sm text-slate-600 font-medium">Loading the comparison…</p>
      </main>,
    )
  }
  if (isError || !data) {
    return shell(
      <main className="max-w-2xl w-full mx-auto px-6 py-16 text-center">
        <h1 className="text-lg font-bold text-slate-800">Comparison not found or access denied.</h1>
        <Link to="/family" className="text-sm text-primary underline mt-3 inline-block">
          Back to family
        </Link>
      </main>,
    )
  }

  const backTo = data.is_head ? "/family" : `/families/${data.family_id}`
  const byMember = data.members.map((m) => ({ member: m, checks: data.checks.filter((c) => c.member_id === m.id) }))
  const busy = decide.isPending || refresh.isPending || close.isPending

  return shell(
    <>
      <section className="px-3.5 sm:px-6 pt-5 pb-3 max-w-[1100px] w-full mx-auto">
        <Link to={backTo} className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline mb-3">
          <ArrowLeftIcon className="size-3.5" />
          {data.is_head ? "Back to family" : "Back to the household"}
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold tracking-widest text-primary uppercase flex items-center gap-1.5">
              <GitCompareArrowsIcon className="size-3" />
              <span>Family comparison · {data.family_name}</span>
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-0.5">
              <span className="font-mono">{data.case_number}</span>
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              {data.check_counts.match} matched
              {data.check_counts.conflict > 0 && (
                <span className="text-destructive font-semibold">
                  {" "}
                  · {data.check_counts.conflict} conflict{data.check_counts.conflict === 1 ? "" : "s"}
                  {data.finding_counts.open > 0 ? ` (${data.finding_counts.open} to decide)` : ""}
                </span>
              )}
              {data.check_counts.not_checked > 0 && <span> · {data.check_counts.not_checked} not checked</span>}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {availableLanguages.length > 0 && (
              <div className="flex items-center gap-1 bg-white border border-border/90 rounded-lg px-2.5 py-1.5 text-xs shadow-2xs">
                <GlobeIcon className="size-3.5 text-muted-foreground shrink-0" />
                <select
                  value={lang}
                  onChange={(e) => {
                    setLang(e.target.value)
                    try {
                      localStorage.setItem("docsure_lang", e.target.value)
                    } catch {
                      // ignore
                    }
                  }}
                  className="bg-transparent border-none text-xs font-semibold focus:outline-hidden cursor-pointer"
                  aria-label="Language"
                >
                  {availableLanguages.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.native_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {data.is_head && (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => refresh.mutate()}
                  className="h-8 text-xs font-semibold gap-1.5"
                >
                  {refresh.isPending ? <Loader2Icon className="size-3.5 animate-spin" /> : <RefreshCwIcon className="size-3.5" />}
                  Run again
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm("Close this comparison? It leaves your list; the record stays.")) close.mutate()
                  }}
                  className="h-8 text-xs text-muted-foreground"
                >
                  Close
                </Button>
              </>
            )}
          </div>
        </div>
      </section>

      <main className="max-w-[1100px] w-full mx-auto px-3.5 sm:px-6 py-4 flex-1 flex flex-col gap-5">
        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-wrap gap-2" aria-label="People compared">
          {data.members.map((m) => (
            <span
              key={m.id}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs shadow-2xs"
            >
              <span className="font-semibold">{m.full_name}</span>
              <span className="text-muted-foreground">({m.is_head ? "head" : m.relation_label})</span>
              <span className="text-muted-foreground">· {m.document_count} doc{m.document_count === 1 ? "" : "s"}</span>
            </span>
          ))}
        </div>

        {data.members.every((m) => m.document_count === 0) && (
          <div role="status" className="rounded-lg border border-blue-200 bg-blue-50/80 px-3 py-2 text-xs text-blue-900">
            None of these people has documents yet, so nothing can be compared. Upload their documents from the family
            page, then choose “Run again”.
          </div>
        )}

        {byMember
          .filter((g) => g.checks.length > 0)
          .map(({ member, checks }) => (
            <section key={member.id} className="rounded-xl border border-border bg-card p-4 shadow-xs flex flex-col gap-3">
              <h2 className="text-sm font-bold">
                {member.full_name}
                <span className="text-muted-foreground font-normal"> · {member.is_head ? "head of family" : member.relation_label}</span>
              </h2>
              <ul className="flex flex-col gap-2">
                {checks.map((check) => (
                  <CheckRow
                    key={`${check.member_id}-${check.check}`}
                    check={check}
                    canReview={data.can_review}
                    busy={busy}
                    onDecide={(c, decision, note) => decide.mutate({ check: c, decision, note })}
                  />
                ))}
              </ul>
            </section>
          ))}

        {data.checks.length === 0 && (
          <p className="text-sm text-muted-foreground">Nothing could be compared yet. Add documents for these members first.</p>
        )}
      </main>
    </>,
  )
}
