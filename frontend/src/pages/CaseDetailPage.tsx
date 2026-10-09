import * as React from "react"
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  ChevronLeftIcon,
  ClockIcon,
  DownloadIcon,
  FileTextIcon,
  GaugeIcon,
  GlobeIcon,
  ShieldCheckIcon,
  UsersIcon,
  PlusIcon,
  Loader2Icon,
  Trash2Icon,
} from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { deleteCase, getCase, getCaseAuditLog, getSignatureMatches, uploadDocument } from "@/api/cases"
import { getCatalog, getLanguages } from "@/api/i18n"
import { getCaseProfile } from "@/api/profiles"
import { useAuth } from "@/hooks/useAuth"
import { useOrganisation } from "@/hooks/useOrganisation"
import { Button } from "@/components/ui/button"
import { Nav } from "@/design-system/Nav"
import { InfoChip } from "@/design-system/InfoChip"
import { SeverityFinding } from "@/design-system/SeverityFinding"
import { ActivityTimeline } from "@/components/case/ActivityTimeline"
import { CaseDecisionPanel } from "@/components/case/CaseDecisionPanel"
import { CaseReportExport } from "@/components/case/CaseReportExport"
import { RiskBadge, TierBadge } from "@/components/case/CaseBadges"
import { DocumentChecksPanel, getCheckOverlays } from "@/components/case/DocumentChecksPanel"
import { IdentityFindingsPanel } from "@/components/case/IdentityFindingsPanel"
import { PdfOverlayViewer } from "@/components/case/PdfOverlayViewer"
import { PersonDetailsPanel } from "@/components/case/PersonDetailsPanel"
import { VerifiedProfilePanel } from "@/components/case/VerifiedProfilePanel"
import { FormsListSection } from "@/components/case/FormsListSection"
import { APP_FULL_NAME, APP_NAME } from "@/lib/appInfo"
import { FileRemovedNotice, PrivateCaseBanner, RetentionBadge } from "@/components/case/RetentionNotice"
import { cn } from "@/lib/utils"
import {
  DOCUMENT_TYPE_LABELS,
  isIdentityCase,
  type BoundingBox,
  type CaseDetailDocument,
  type IdentityExtractedFields,
  type SignatureMatch,
} from "@/types/case"
import { hasRank, isPlatformAdmin } from "@/types/auth"

// Card colours by risk tier: low = green, medium = amber, high = red, and a
// neutral slate while the case is still being analysed.
const FLAG_CARD_CLASSES: Record<string, string> = {
  low: "bg-emerald-50 border-emerald-200",
  medium: "bg-amber-50 border-amber-200",
  high: "bg-red-50 border-red-200",
  pending: "bg-slate-50 border-slate-200",
}
const FLAG_ICON_CLASSES: Record<string, string> = {
  low: "bg-emerald-100 text-emerald-600",
  medium: "bg-amber-100 text-amber-600",
  high: "bg-red-100 text-red-600",
  pending: "bg-slate-100 text-slate-500",
}
const FLAG_TITLE_CLASSES: Record<string, string> = {
  low: "text-emerald-900",
  medium: "text-amber-900",
  high: "text-red-900",
  pending: "text-slate-700",
}
const FLAG_TEXT_CLASSES: Record<string, string> = {
  low: "text-emerald-700",
  medium: "text-amber-700",
  high: "text-red-700",
  pending: "text-slate-500",
}

const SEVERITY_TONE: Record<string, "negative" | "warning" | "positive"> = {
  critical: "negative",
  high: "negative",
  medium: "warning",
  low: "positive",
  info: "positive",
}

// The "Explainable findings" panel lists the risk assessment's fired rules
// (highest weight first) — the same reasons and weights that produced the
// score, frozen at scoring time (backend/app/models/case_risk_assessment.py).
// Capped so one noisy case doesn't bury the rest; every underlying finding is
// still in the Document checks panel.
const EXPLAINABLE_FINDINGS_DISPLAY_CAP = 8

function countCompleteCoreFields(coreFields: CaseDetailDocument["extracted_fields"]): { filled: number; total: number } {
  if (!coreFields) return { filled: 0, total: 0 }
  const values = Object.values(coreFields.core_fields)
  return { filled: values.filter((v) => v && v.value !== null && v.value !== undefined).length, total: values.length }
}

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const { token, user } = useAuth()
  const [selectedDocIndex, setSelectedDocIndex] = React.useState<number>(0)
  const [detailsView, setDetailsView] = React.useState<"profile" | "document">("profile")
  const [currentLang, setCurrentLang] = React.useState<string>(() => {
    try {
      return localStorage.getItem("docsure_lang") || localStorage.getItem("agnitia_lang") || "en"
    } catch {
      return "en"
    }
  })

  React.useEffect(() => {
    try {
      localStorage.setItem("docsure_lang", currentLang)
    } catch {
      // ignore
    }
  }, [currentLang])

  React.useEffect(() => {
    setSelectedDocIndex(0)
    setViewerFile(null)
  }, [caseId])

  const [selectedBox, setSelectedBox] = React.useState<BoundingBox | null>(null)
  const { isOrgSite } = useOrganisation()
  const isReady = Boolean(caseId && token)
  // Submitters never receive their own case's risk tier/score/reasons (the
  // backend withholds them); the risk cards are reviewer/admin-only.
  // Platform admins see the same evidence as reviewers (read-only support
  // access, audited server-side) but never act or generate reports.
  const isSupportView = isPlatformAdmin(user?.role)
  const isReviewerRole = hasRank(user?.role, "reviewer_l1") || isSupportView
  const canExport = hasRank(user?.role, "reviewer_l1")
  const shouldShowReviewerPanel = Boolean(isOrgSite || isReviewerRole)

  // Available languages from GET /i18n/languages (public)
  const { data: languages = [] } = useQuery({
    queryKey: ["i18nLanguages"],
    queryFn: () => getLanguages(),
    staleTime: 5 * 60 * 1000,
  })

  // Offer only languages where available === true
  const availableLanguages = React.useMemo(() => {
    return languages.filter((l) => l.available)
  }, [languages])

  // Catalog of translated machine labels from GET /i18n/catalog?lang=<code>
  const { data: catalog = null } = useQuery({
    queryKey: ["i18nCatalog", currentLang, token],
    queryFn: () => (token ? getCatalog(currentLang, token) : Promise.resolve(null)),
    enabled: Boolean(token),
    staleTime: 5 * 60 * 1000,
  })

  const {
    data: caseDetail,
    isLoading: isCaseLoading,
    isError: isCaseError,
  } = useQuery({
    queryKey: ["case", caseId, token, currentLang],
    queryFn: () => getCase(caseId!, token!, currentLang),
    enabled: isReady,
    // Poll while the automated pipeline is still running so "Analyzing"
    // resolves into a tier (and Approve unlocks) without a manual refresh.
    // Stop polling once the pipeline finishes, or as soon as the case reaches
    // manual review or terminal status. Submitters never receive an assessment
    // object (redacted server-side), so their polling stops as soon as pipeline.complete is true.
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false

      const isAnalyzing =
        data.status === "submitted" || data.status === "under_automated_review"
      if (!isAnalyzing) {
        return false
      }

      if (!data.pipeline.complete) {
        return 5_000
      }

      // Reviewers wait briefly for risk assessment calculation if pipeline just finished.
      if (isReviewerRole && data.assessment === null) {
        return 5_000
      }

      return false
    },
  })

  // The backend says who may settle conflicts: a reviewer, the head of the case's family, or the
  // submitter of a case outside any family. A family member signed in on their own may not.
  // The corporate decision panel (approve/reject/escalate) stays hidden outside reviewers.
  const canManage = Boolean(caseDetail?.can_manage)

  const { data: auditLog, isLoading: isAuditLoading } = useQuery({
    queryKey: ["caseAuditLog", caseId, token],
    queryFn: () => getCaseAuditLog(caseId!, token!),
    enabled: isReady,
  })

  // In-case signature comparison results — fetched case-wide and filtered
  // per active document in the Checks panel. Only in_case scope is shown
  // at this phase (library-scope comparison not built yet per SPECIFICATION.md §2.3).
  const { data: signatureMatches = [] } = useQuery<SignatureMatch[]>({
    queryKey: ["signatureMatches", caseId, token],
    queryFn: () => getSignatureMatches(caseId!, token!),
    enabled: isReady,
    // Refetch so results appear after the Celery task completes —
    // comparison is enqueued async after reference creation.
    // Stop polling once the automated pipeline is complete.
    refetchInterval: () => (!caseDetail?.pipeline.complete ? 10_000 : false),
    refetchIntervalInBackground: false,
  })

  const documents: CaseDetailDocument[] = caseDetail?.documents ?? []
  const activeDoc = documents[selectedDocIndex] ?? documents[0] ?? null

  // Every GET /cases/{id} mints a fresh SAS URL for each file, and this page
  // re-fetches the case while it is processing. react-pdf treats a new URL as
  // a new file: it reloads and suspends again each time. Keep the first URL
  // per document for the viewer while the page is open (the SAS is valid for
  // 15 minutes and pdf.js keeps the loaded file).
  const [viewerFile, setViewerFile] = React.useState<{ docId: string; url: string | null } | null>(null)
  if (activeDoc && viewerFile?.docId !== activeDoc.id) {
    // Adjusting state during render when the selected document changes
    // (React's supported pattern); later refetches keep the stored URL.
    setViewerFile({ docId: activeDoc.id, url: activeDoc.file_url })
  }
  const viewerUrl =
    activeDoc && viewerFile?.docId === activeDoc.id ? viewerFile.url : activeDoc?.file_url

  const queryClient = useQueryClient()
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)
  const [uploadError, setUploadError] = React.useState<string | null>(null)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = React.useState(false)
  const navigate = useNavigate()

  // A family comparison has its own screen.
  React.useEffect(() => {
    if (caseDetail?.case_type === "family_comparison") {
      navigate(`/family/compare/${caseDetail.id}`, { replace: true })
    }
  }, [caseDetail?.case_type, caseDetail?.id, navigate])

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!caseId || !token) throw new Error("Missing case ID or token")
      return deleteCase(caseId, token)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cases"] })
      void queryClient.invalidateQueries({ queryKey: ["family"] })
      navigate("/cases")
    },
  })

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!caseId || !token) throw new Error("Missing case ID or token")
      return uploadDocument(caseId, file, token)
    },
    onSuccess: () => {
      setUploadError(null)
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] })
      void queryClient.invalidateQueries({ queryKey: ["caseProfile", caseId] })
      void queryClient.invalidateQueries({ queryKey: ["cases"] })
      void queryClient.invalidateQueries({ queryKey: ["family"] })
    },
    onError: (err: any) => {
      setUploadError(err?.message || "Failed to upload document")
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadMutation.mutate(file)
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const isIdentity = isIdentityCase(caseDetail?.case_type) || activeDoc?.extracted_fields?.schema === "identity"

  const { data: caseProfile = null, isLoading: isProfileLoading } = useQuery({
    queryKey: ["caseProfile", caseId, token],
    queryFn: () => (caseId && token ? getCaseProfile(caseId, token) : Promise.resolve(null)),
    enabled: Boolean(isReady && isIdentity),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      return !data.checks_complete ? 5_000 : false
    },
  })

  // Filter signature matches to those comparing AGAINST the active document
  // (i.e. document_id = activeDoc.id — the target, not the reference source).
  const activeDocSignatureMatches: SignatureMatch[] = activeDoc
    ? signatureMatches.filter((m) => m.document_id === activeDoc.id)
    : []

  const reasons = caseDetail?.assessment?.triggered_reasons ?? []
  const visibleReasons = reasons.slice(0, EXPLAINABLE_FINDINGS_DISPLAY_CAP)
  const hiddenReasonCount = reasons.length - visibleReasons.length

  // The case's cross_document_findings, but scoped to
  // the selected document and unfiltered by severity/display cap — the
  // full-detail counterpart to that case-wide summary, living next to
  // Document checks since a cross-document comparison is conceptually
  // another check that ran against this document, just a case-level one.
  const activeDocCrossFindings = activeDoc
    ? (caseDetail?.cross_document_findings ?? []).filter((f) => f.document_ids?.includes(activeDoc.id))
    : []

  if (isCaseError) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="cases" />
        <main className="max-w-2xl w-full mx-auto px-6 py-16 text-center">
          <h1 className="text-lg font-bold text-slate-800">Case not found</h1>
          <p className="text-sm text-slate-500 mt-2">
            This case doesn't exist, or you don't have access to it.
          </p>
          <Link to="/cases" className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:underline mt-4">
            <ChevronLeftIcon className="w-4 h-4" />
            Back to queue
          </Link>
        </main>
      </div>
    )
  }

  const isRtl = (catalog?.direction || availableLanguages.find((l) => l.code === currentLang)?.direction) === "rtl"

  const overallSeverityScore = React.useMemo(() => {
    if (caseDetail?.assessment?.score !== undefined && caseDetail.assessment?.score !== null) {
      return caseDetail.assessment.score
    }
    if (caseDetail?.flag?.score !== undefined && caseDetail.flag?.score !== null) {
      return caseDetail.flag.score
    }
    if (caseDetail?.cross_document_findings && caseDetail.cross_document_findings.length > 0) {
      const activeConflicts = caseDetail.cross_document_findings.filter((f) => f.classification === "conflict")
      if (activeConflicts.length > 0) {
        return Math.max(
          ...activeConflicts.map((f) => {
            if (typeof f.severity_score === "number" && f.severity_score > 0) return f.severity_score
            switch (f.severity) {
              case "critical":
                return f.field_name === "full_name" || f.field_name === "photo" ? 95 : 90
              case "high":
                return f.field_name === "date_of_birth" || f.field_name === "gender" ? 75 : 70
              case "medium":
                return 50
              case "low":
                return 25
              default:
                return 0
            }
          })
        )
      }
    }
    return 0
  }, [caseDetail])

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900 antialiased selection:bg-blue-100 selection:text-blue-900"
    >
      <Nav active="cases" />

      <section className="px-3.5 sm:px-6 pt-4 sm:pt-5 pb-3 max-w-[1680px] w-full mx-auto">
        <Link
          to={!isOrgSite && !isReviewerRole ? (isIdentity ? "/family" : "/my-cases") : "/cases"}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors mb-2"
        >
          <ChevronLeftIcon className="w-3.5 h-3.5" />
          <span>{!isOrgSite && !isReviewerRole ? (isIdentity ? "Back to family" : "Back to my cases") : "Back to queue"}</span>
        </Link>

        {caseDetail?.delete_on_logout && (
          <div className="mb-3">
            <PrivateCaseBanner dataRemovedAt={caseDetail.data_removed_at} />
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold tracking-widest text-blue-700 uppercase">
              {isIdentity ? "Identity Verification" : "Case Investigation"}
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mt-0.5">
              {isCaseLoading ? "Loading..." : caseDetail?.case_number ?? "—"}
            </h1>
            {caseDetail && (
              <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5 flex-wrap">
                <span>{caseDetail.submitted_by?.full_name || caseDetail.submitted_by?.email}</span>
                <span className="text-slate-300">·</span>
                <span>{documents.length} document{documents.length === 1 ? "" : "s"} attached</span>
                {isIdentity ? (
                  <>
                    <span className="text-slate-300">·</span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border shadow-2xs",
                        overallSeverityScore >= 80
                          ? "bg-red-50 text-red-700 border-red-300 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800"
                          : overallSeverityScore >= 60
                          ? "bg-orange-50 text-orange-700 border-orange-300 dark:bg-orange-950/40 dark:text-orange-300 dark:border-orange-800"
                          : overallSeverityScore >= 40
                          ? "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800"
                          : overallSeverityScore >= 15
                          ? "bg-blue-50 text-blue-700 border-blue-300 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800"
                          : "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                      )}
                      title={`Case Overall Severity Score: ${overallSeverityScore}/100`}
                    >
                      <GaugeIcon className="size-3.5" />
                      <span>Severity Score: {overallSeverityScore}/100</span>
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-slate-300">·</span>
                    <RiskBadge tier={caseDetail.risk_tier} compact />
                  </>
                )}
                {caseDetail.family_member && (
                  <>
                    <span className="text-slate-300">·</span>
                    <Link
                      to={`/families/${caseDetail.family_member.family_id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors"
                      title="View Household"
                    >
                      <UsersIcon className="size-3 text-blue-600" />
                      <span>{caseDetail.family_member.full_name} ({caseDetail.family_member.relation})</span>
                    </Link>
                  </>
                )}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {/* Language Selector */}
            {availableLanguages.length > 0 && (
              <div className="flex items-center gap-1.5 bg-white border border-slate-200/90 rounded-lg px-2.5 py-1.5 text-xs shadow-2xs">
                <GlobeIcon className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <select
                  value={currentLang}
                  onChange={(e) => setCurrentLang(e.target.value)}
                  className="bg-transparent border-none text-xs font-semibold text-slate-700 focus:outline-hidden cursor-pointer"
                  aria-label="Interface language"
                >
                  {availableLanguages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.native_name} {lang.native_name !== lang.name ? `(${lang.name})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {canExport && caseId && token && <CaseReportExport caseId={caseId} token={token} />}
            {caseDetail && !isIdentity && <TierBadge tier={caseDetail.assigned_tier} />}
            {caseDetail && !isSupportView && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDeleteModalOpen(true)}
                title="Delete this case (history is preserved)"
                className="h-8.5 px-3 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 gap-1.5"
              >
                <Trash2Icon className="size-3.5" />
                <span>Delete case</span>
              </Button>
            )}
          </div>
        </div>
      </section>

      <main className="max-w-[1680px] w-full mx-auto px-3.5 sm:px-6 py-4 flex-1 flex flex-col gap-5 sm:gap-6">
        {isSupportView && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-2.5 text-xs text-amber-900">
            <span className="font-semibold">Support view — read-only.</span> You are viewing another company's
            case as a platform admin. This access is recorded in the platform audit log (the company does not see it).
          </div>
        )}

        {isIdentity ? (
          /* ================= IDENTITY CASE 2-COLUMN LAYOUT ================= */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 items-start">
            {/* LEFT COLUMN: ~60% (col-span-7) Document Tabs + Viewer */}
            <div className="lg:col-span-7 flex flex-col gap-3 min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto custom-scrollbar">
              {/* Document Tabs across the top with conflict badges */}
              <div className="bg-white rounded-xl border border-slate-200/80 p-2.5 shadow-2xs">
                <div className="flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth">
                  {documents.map((doc, idx) => {
                    const isSelected = selectedDocIndex === idx
                    const label = doc.document_type
                      ? catalog?.documents?.[doc.document_type] ?? DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type
                      : `Document ${idx + 1}`

                    // Count unresolved conflicts involving this document
                    const conflictCount = (caseDetail?.cross_document_findings ?? []).filter(
                      (f) => f.classification === "conflict" && f.document_ids?.includes(doc.id)
                    ).length

                    return (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() => setSelectedDocIndex(idx)}
                        title={doc.original_filename}
                        className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold shrink-0 transition-all ${
                          isSelected
                            ? "bg-primary text-primary-foreground shadow-xs"
                            : "bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground"
                        }`}
                      >
                        <FileTextIcon className="size-3.5 shrink-0" />
                        <span className="truncate max-w-[160px]">{label}</span>
                        {conflictCount > 0 && (
                          <span
                            title={`${conflictCount} conflict${conflictCount === 1 ? "" : "s"} involving this document`}
                            className={`inline-flex items-center justify-center size-4.5 rounded-full text-[10px] font-bold ${
                              isSelected
                                ? "bg-white text-destructive shadow-2xs"
                                : "bg-red-600 text-white"
                            }`}
                          >
                            {conflictCount}
                          </span>
                        )}
                        {doc.processing_status === "processing" && (
                          <span className="size-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                        )}
                      </button>
                    )
                  })}

                  {/* Add another document to this person's bundle */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".pdf,.png,.jpg,.jpeg,.tiff"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={uploadMutation.isPending}
                    onClick={() => fileInputRef.current?.click()}
                    className="h-8.5 px-3 text-xs font-semibold shrink-0 gap-1.5 border-dashed border-primary/40 text-primary hover:bg-primary/5 hover:border-primary transition"
                  >
                    {uploadMutation.isPending ? (
                      <>
                        <Loader2Icon className="size-3.5 animate-spin" />
                        <span>Uploading…</span>
                      </>
                    ) : (
                      <>
                        <PlusIcon className="size-3.5" />
                        <span>+ Add document to profile</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {uploadError && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive flex items-center justify-between">
                  <span>{uploadError}</span>
                  <button type="button" onClick={() => setUploadError(null)} className="font-bold underline text-[11px]">
                    Dismiss
                  </button>
                </div>
              )}

              {/* Document Header & Viewer */}
              {!activeDoc ? (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center text-sm text-slate-400">
                  {isCaseLoading ? "Loading document..." : "No document selected."}
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Document {String(selectedDocIndex + 1).padStart(2, "0")} of {documents.length}
                      </span>
                      <h2 className="text-sm font-bold text-slate-800">
                        {activeDoc.document_type
                          ? catalog?.documents?.[activeDoc.document_type] ?? DOCUMENT_TYPE_LABELS[activeDoc.document_type] ?? activeDoc.document_type
                          : activeDoc.original_filename}
                      </h2>
                      <p className="text-[11px] text-slate-500 font-mono mt-0.5" title={activeDoc.original_filename}>
                        {activeDoc.original_filename}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex flex-col items-end gap-1">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                          activeDoc.processing_status === "complete"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : activeDoc.processing_status === "failed"
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}>
                          {activeDoc.processing_status === "complete"
                            ? "Processed"
                            : activeDoc.processing_status === "failed"
                            ? "Failed"
                            : "Processing"}
                        </span>
                        {activeDoc.processing_status === "failed" && activeDoc.processing_error && (
                          <span className="text-[11px] text-red-600 bg-red-50/80 px-2 py-0.5 rounded border border-red-200/60 max-w-xs text-right font-medium" title={activeDoc.processing_error}>
                            {activeDoc.processing_error}
                          </span>
                        )}
                      </div>
                      <RetentionBadge expiresAt={activeDoc.file_expires_at} />
                      {activeDoc.file_url && (
                        <a
                          href={activeDoc.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                          title="Download or open original file"
                        >
                          <DownloadIcon className="w-4 h-4" />
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="mt-3">
                    {activeDoc.file_url ? (
                      <PdfOverlayViewer
                        fileUrl={viewerUrl ?? activeDoc.file_url}
                        originalFilename={activeDoc.original_filename}
                        overlays={[]}
                        selectedBox={selectedBox}
                      />
                    ) : (
                      <FileRemovedNotice dataRemoved={Boolean(caseDetail?.data_removed_at)} />
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT COLUMN: ~40% (col-span-5) Identity Findings + Person Details Panel with independent scroll */}
            <div className="lg:col-span-5 flex flex-col gap-5 min-w-0 lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto lg:pr-2 custom-scrollbar">
              {/* Household context banner if case is linked to a family member */}
              {caseDetail?.family_member && (
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-blue-50/60 border border-blue-200/80 text-xs text-foreground">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg bg-blue-100 text-blue-700">
                      <UsersIcon className="size-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-blue-950">
                        Household: {caseDetail.family_member.full_name} ({caseDetail.family_member.relation})
                      </p>
                      <p className="text-[11px] text-blue-700">
                        Cross-member consistency checks are active for this family.
                      </p>
                    </div>
                  </div>
                  <Link
                    to={`/families/${caseDetail.family_member.family_id}`}
                    className="text-xs font-semibold text-blue-700 hover:underline shrink-0"
                  >
                    View family →
                  </Link>
                </div>
              )}

              {/* Contradictions & Differences Panel */}
              <IdentityFindingsPanel
                findings={caseDetail?.cross_document_findings ?? []}
                documents={documents}
                isProcessing={!caseDetail?.pipeline.complete}
                caseId={caseDetail?.id}
                canAct={Boolean(caseDetail?.can_act || canManage)}
                caseStatus={caseDetail?.status}
                findingCounts={caseDetail?.finding_counts}
                catalog={catalog}
                currentLang={currentLang}
                token={token}
              />

              {/* Profile View Switcher: "Verified profile" vs "Per document" */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 p-1 bg-muted/60 rounded-lg text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => setDetailsView("profile")}
                    className={cn(
                      "px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5",
                      detailsView === "profile"
                        ? "bg-card text-foreground shadow-2xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <ShieldCheckIcon className="size-3.5 text-primary" />
                    <span>Verified profile</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDetailsView("document")}
                    className={cn(
                      "px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5",
                      detailsView === "document"
                        ? "bg-card text-foreground shadow-2xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <FileTextIcon className="size-3.5" />
                    <span>Per document</span>
                  </button>
                </div>
              </div>

              {/* Verified Profile Card OR Per-document Person details panel */}
              {detailsView === "profile" ? (
                <VerifiedProfilePanel
                  profile={caseProfile}
                  isLoading={isProfileLoading}
                  caseId={caseId!}
                  canAct={Boolean(caseDetail?.can_act || canManage)}
                  caseStatus={caseDetail?.status}
                  documents={documents}
                  catalog={catalog}
                  currentLang={currentLang}
                  token={token}
                />
              ) : (
                <PersonDetailsPanel
                  extractedFields={
                    activeDoc?.extracted_fields?.schema === "identity"
                      ? (activeDoc.extracted_fields as IdentityExtractedFields)
                      : null
                  }
                  processingStatus={activeDoc?.processing_status}
                  processingError={activeDoc?.processing_error}
                  selectedBox={selectedBox}
                  onSelectField={(box) => setSelectedBox(box)}
                  catalog={catalog}
                />
              )}

              {/* Fill a form section */}
              <FormsListSection
                caseId={caseId!}
                caseType={caseDetail?.case_type}
                currentLang={currentLang}
                token={token}
              />

              {caseDetail && token && shouldShowReviewerPanel && (
                <CaseDecisionPanel caseDetail={caseDetail} role={user?.role} token={token} />
              )}
            </div>
          </div>
        ) : (
          /* ================= INVOICE / CLAIM CASE 3-COLUMN LAYOUT ================= */
          <>
            {/* Mobile / Tablet Evidence Switcher (< lg) */}
            {documents.length > 1 && (
              <div className="lg:hidden flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth pb-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 shrink-0">
                  Evidence:
                </span>
                {documents.map((doc, idx) => {
                  const isSelected = selectedDocIndex === idx
                  const failed = doc.checks?.some((c) => c.status === "failed")
                  return (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => setSelectedDocIndex(idx)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 whitespace-nowrap transition border ${
                        isSelected
                          ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                          : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      <span className={`size-1.5 rounded-full ${isSelected ? "bg-white" : failed ? "bg-rose-500" : "bg-emerald-500"}`} />
                      <span className="max-w-[140px] truncate">{doc.original_filename}</span>
                    </button>
                  )
                })}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6">
              {/* LEFT SIDEBAR: Documents & Case Flags */}
              <aside aria-label="Documents in Case" className="lg:col-span-3 flex flex-col space-y-4">
                {isCaseLoading && (
                  <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm text-xs text-slate-400">
                    Loading case...
                  </div>
                )}
                {caseDetail && isReviewerRole && (
                  <div className={`border rounded-xl p-4 shadow-sm ${FLAG_CARD_CLASSES[caseDetail.flag.flag]}`}>
                    <div className="flex items-start space-x-3">
                      <div className={`w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center mt-0.5 ${FLAG_ICON_CLASSES[caseDetail.flag.flag]}`}>
                        {caseDetail.flag.flag === "low" ? (
                          <CheckCircle2Icon className="w-4 h-4" />
                        ) : caseDetail.flag.flag === "pending" ? (
                          <ClockIcon className="w-4 h-4" />
                        ) : (
                          <AlertTriangleIcon className="w-4 h-4" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className={`text-xs font-bold leading-tight ${FLAG_TITLE_CLASSES[caseDetail.flag.flag]}`}>
                          {caseDetail.flag.label}
                          {caseDetail.flag.score !== null && (
                            <span className="ml-1.5 font-mono font-semibold opacity-70">{caseDetail.flag.score}/100</span>
                          )}
                        </h3>
                        <p className={`text-xs leading-relaxed mt-2 break-words [overflow-wrap:anywhere] ${FLAG_TEXT_CLASSES[caseDetail.flag.flag]}`}>
                          {caseDetail.flag.description}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="hidden lg:flex bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm flex-col flex-1">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Documents ({documents.length})
                    </span>
                  </div>
                  <div className="space-y-2.5">
                    {documents.length === 0 && !isCaseLoading && (
                      <p className="text-xs text-slate-400 py-4 text-center">No documents uploaded yet.</p>
                    )}
                    {documents.map((doc, idx) => {
                      const isSelected = selectedDocIndex === idx
                      const totalChecks = doc.checks?.length ?? 0
                      const resultOf = (c: { status: string; result: Record<string, unknown> | null }) =>
                        c.status === "completed" ? String(c.result?.result ?? "") : c.status
                      const countOf = (r: string) => doc.checks?.filter((c) => resultOf(c) === r).length ?? 0
                      const flaggedChecks = countOf("flag")
                      const passedChecks = countOf("pass")
                      const limitedChecks = countOf("limited")
                      const failedChecks = countOf("failed")
                      const docTypeLabel = doc.document_type
                        ? DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type
                        : "Classification pending"
                      const statusParts = [
                        flaggedChecks > 0 && `${flaggedChecks} flagged`,
                        limitedChecks > 0 && `${limitedChecks} limited`,
                        failedChecks > 0 && `${failedChecks} failed to run`,
                        passedChecks > 0 && `${passedChecks} passed`,
                      ].filter(Boolean)
                      const statusText =
                        totalChecks === 0
                          ? "No checks run yet"
                          : flaggedChecks + limitedChecks + failedChecks === 0
                          ? `All ${passedChecks} check${passedChecks === 1 ? "" : "s"} passed`
                          : statusParts.join(" · ")

                      return (
                        <div
                          key={doc.id}
                          onClick={() => setSelectedDocIndex(idx)}
                          className={`relative rounded-lg p-3 cursor-pointer shadow-sm transition-colors ${
                            isSelected
                              ? "bg-blue-50/70 border-2 border-blue-600"
                              : "border border-slate-200 hover:bg-slate-50"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-start space-x-2.5 min-w-0">
                              <div className={`w-8 h-8 rounded flex items-center justify-center flex-shrink-0 ${
                                isSelected ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"
                              }`}>
                                <FileTextIcon className="w-4 h-4" />
                              </div>
                              <div className="min-w-0">
                                <h4 className="text-xs font-bold text-slate-900 leading-tight truncate" title={doc.original_filename}>
                                  {doc.original_filename}
                                </h4>
                                <p className="text-[11px] text-slate-500 font-medium mt-0.5">
                                  {docTypeLabel}
                                </p>
                                <div className="flex items-center gap-1.5 mt-2">
                                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                    totalChecks === 0
                                      ? "bg-slate-300"
                                      : flaggedChecks + failedChecks > 0
                                      ? "bg-red-500"
                                      : limitedChecks > 0
                                      ? "bg-amber-500"
                                      : "bg-emerald-500"
                                  }`}></span>
                                  <span className={`text-[10px] font-semibold ${flaggedChecks + failedChecks > 0 ? "text-red-600" : "text-slate-600"}`}>
                                    {statusText}
                                  </span>
                                </div>
                              </div>
                            </div>
                            {isSelected && (
                              <span className="text-[10px] font-bold bg-blue-600 text-white px-1.5 py-0.5 rounded flex-shrink-0">Active</span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </aside>

              {/* CENTER COLUMN: Document Detail + Checks */}
              <section aria-label="Document Detail and Checks" className="lg:col-span-5 flex flex-col space-y-3">
                {!activeDoc ? (
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center text-sm text-slate-400">
                    {isCaseLoading ? "Loading document..." : "No document selected."}
                  </div>
                ) : (
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col">
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Evidence {String(selectedDocIndex + 1).padStart(2, "0")}
                        </span>
                        <h2 className="text-sm font-bold text-slate-800">
                          {DOCUMENT_TYPE_LABELS[activeDoc.document_type ?? ""] ?? activeDoc.original_filename}
                        </h2>
                      </div>
                      <div className="flex items-center gap-2">
                        <RetentionBadge expiresAt={activeDoc.file_expires_at} />
                        {activeDoc.file_url && (
                          <a
                            href={activeDoc.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                            title="Download or open original file"
                          >
                            <DownloadIcon className="w-4 h-4" />
                          </a>
                        )}
                      </div>
                    </div>

                    <div className="mt-3">
                      {activeDoc.file_url ? (
                        <PdfOverlayViewer fileUrl={viewerUrl ?? activeDoc.file_url} overlays={getCheckOverlays(activeDoc.checks, caseDetail?.cross_document_findings ?? [], activeDoc.id)} />
                      ) : (
                        <FileRemovedNotice dataRemoved={Boolean(caseDetail?.data_removed_at)} />
                      )}
                    </div>

                    {/* Extracted fields */}
                    <div className="mt-3">
                      {!activeDoc.extracted_fields ? (
                        <div className="bg-slate-50 rounded-lg border border-slate-200/70 p-4 text-center text-xs text-slate-400">
                          {activeDoc.processing_status === "failed"
                            ? `Extraction failed${activeDoc.processing_error ? `: ${activeDoc.processing_error}` : "."}`
                            : "Extraction pending — OCR and field extraction haven't completed yet."}
                        </div>
                      ) : (
                        <div className="bg-slate-50 rounded-lg border border-slate-200/70 p-4">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                              Extracted fields
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              Classification confidence: {(activeDoc.extracted_fields.document_type_confidence * 100).toFixed(1)}%
                            </span>
                          </div>
                          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Issuer</dt>
                              <dd className="font-semibold text-slate-800 truncate">
                                {activeDoc.extracted_fields.core_fields?.issuer?.value ?? "—"}
                                {activeDoc.extracted_fields.core_fields?.issuer?.uncertain && (
                                  <span className="ml-1 text-amber-600 font-normal">(uncertain)</span>
                                )}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Reference #</dt>
                              <dd className="font-semibold text-slate-800 truncate">
                                {activeDoc.extracted_fields.core_fields?.reference_number?.value ?? "—"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Date</dt>
                              <dd className="font-semibold text-slate-800 truncate">
                                {activeDoc.extracted_fields.core_fields?.date?.value ??
                                  activeDoc.extracted_fields.core_fields?.date?.raw_text ??
                                  "—"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Subtotal</dt>
                              <dd className="font-semibold text-slate-800 truncate">
                                {activeDoc.extracted_fields.core_fields?.subtotal?.value != null
                                  ? `${activeDoc.extracted_fields.core_fields.subtotal.currency ?? ""} ${activeDoc.extracted_fields.core_fields.subtotal.value.toLocaleString()}`
                                  : "—"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Tax</dt>
                              <dd className="font-semibold text-slate-800 truncate">
                                {activeDoc.extracted_fields.core_fields?.tax_amount?.value != null
                                  ? `${activeDoc.extracted_fields.core_fields.tax_amount.currency ?? ""} ${activeDoc.extracted_fields.core_fields.tax_amount.value.toLocaleString()}`
                                  : "—"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[10px] uppercase font-bold text-slate-400">Total</dt>
                              <dd className="font-bold text-slate-900 truncate">
                                {activeDoc.extracted_fields.core_fields?.amount?.value != null
                                  ? `${activeDoc.extracted_fields.core_fields.amount.currency ?? ""} ${activeDoc.extracted_fields.core_fields.amount.value.toLocaleString()}`
                                  : "—"}
                              </dd>
                            </div>
                          </dl>
                          {activeDoc.extracted_fields.additional_fields?.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-slate-200/70 space-y-1">
                              {activeDoc.extracted_fields.additional_fields.map((f, i) => (
                                <div key={i} className="flex justify-between text-[11px] font-mono text-slate-600">
                                  <span className="truncate">{f.field_name}</span>
                                  <span className="font-semibold text-slate-800">{f.value ?? "—"}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Bottom Metadata Strip */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-3 mt-3 border-t border-slate-100 text-xs">
                      <InfoChip
                        caption="File integrity"
                        icon={CheckCircle2Icon}
                        value={<span className="font-mono">{activeDoc.file_hash.slice(0, 12)}...</span>}
                      />
                      <InfoChip
                        caption="Classification"
                        value={activeDoc.document_type ? DOCUMENT_TYPE_LABELS[activeDoc.document_type] ?? activeDoc.document_type : "Pending"}
                      />
                      <InfoChip
                        caption="Extraction"
                        value={
                          activeDoc.extracted_fields
                            ? (() => {
                                const { filled, total } = countCompleteCoreFields(activeDoc.extracted_fields)
                                return `${filled} / ${total} fields`
                              })()
                            : activeDoc.processing_status
                        }
                      />
                    </div>
                  </div>
                )}
              </section>

              {/* RIGHT COLUMN: Risk & Findings */}
              <section aria-label="Risk and Explainable Findings" className="lg:col-span-4 flex flex-col space-y-4 min-w-0">
                {isReviewerRole && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Risk assessment</span>
                    {caseDetail && <RiskBadge tier={caseDetail.assessment?.tier ?? null} />}
                  </div>
                  {caseDetail?.assessment ? (
                    <>
                      <div className="mt-3 flex items-baseline gap-1.5">
                        <span className="text-4xl font-extrabold tracking-tight text-slate-900">{caseDetail.assessment.score}</span>
                        <span className="text-sm font-semibold text-slate-400">/ 100</span>
                      </div>
                      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={
                            caseDetail.assessment.tier === "high"
                              ? "h-2 rounded-full bg-red-500"
                              : caseDetail.assessment.tier === "medium"
                                ? "h-2 rounded-full bg-amber-500"
                                : "h-2 rounded-full bg-emerald-500"
                          }
                          style={{ width: `${caseDetail.assessment.score}%` }}
                        />
                      </div>
                      <p className="text-[11px] text-slate-400 mt-2 leading-relaxed break-words [overflow-wrap:anywhere]">
                        Sum of the weights of {caseDetail.assessment.triggered_reasons.length} triggered rule
                        {caseDetail.assessment.triggered_reasons.length === 1 ? "" : "s"}
                        {caseDetail.assessment.group_caps?.metadata
                          ? ` (metadata rules: ${caseDetail.assessment.group_caps.metadata.points} points, counted as ${caseDetail.assessment.group_caps.metadata.cap})`
                          : ""}
                        , capped at 100. Tiers: medium from{" "}
                        {caseDetail.assessment.thresholds.medium ?? "—"}, high from {caseDetail.assessment.thresholds.high ?? "—"}
                        {" "}(as configured when scored). Advisory — for reviewer use.
                      </p>
                    </>
                  ) : caseDetail ? (
                    <p className="text-[11px] text-slate-500 mt-2 leading-relaxed break-words [overflow-wrap:anywhere]">
                      Analyzing — the risk score appears once every automated check for this case has finished.
                      {caseDetail.pipeline.pending.length > 0 && (
                        <span className="block mt-1 text-slate-400">
                          Waiting on: {caseDetail.pipeline.pending.slice(0, 3).join("; ")}
                          {caseDetail.pipeline.pending.length > 3 ? ` (+${caseDetail.pipeline.pending.length - 3} more)` : ""}
                        </span>
                      )}
                    </p>
                  ) : null}
                </div>
                )}

                {caseDetail && token && shouldShowReviewerPanel && (
                  <CaseDecisionPanel caseDetail={caseDetail} role={user?.role} token={token} />
                )}

                {isReviewerRole && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col flex-1 min-w-0">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                      Explainable findings
                    </h3>
                    <span className="text-xs font-semibold text-slate-400">
                      {reasons.length} signal{reasons.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="space-y-3.5 min-w-0">
                    {!caseDetail ? (
                      <p className="text-xs text-slate-400">Loading...</p>
                    ) : !caseDetail.assessment ? (
                      <p className="text-xs text-slate-400">Findings appear here once the automated checks finish.</p>
                    ) : reasons.length === 0 ? (
                      <p className="text-xs text-slate-400">No risk signals fired for this case.</p>
                    ) : (
                      <>
                        {visibleReasons.map((r, i) => (
                          <SeverityFinding
                            key={`${r.rule_id}:${r.document_id ?? "case"}:${i}`}
                            title={r.title || r.rule_id}
                            description={r.short || r.reason}
                            detail={r.short ? r.reason : undefined}
                            pointDelta={r.weight}
                            tone={SEVERITY_TONE[r.severity] ?? "warning"}
                          />
                        ))}
                        {hiddenReasonCount > 0 && (
                          <p className="text-[11px] text-slate-400 pt-1 break-words [overflow-wrap:anywhere]">
                            +{hiddenReasonCount} more lower-weight signal{hiddenReasonCount === 1 ? "" : "s"} contributed to the score.
                          </p>
                        )}
                      </>
                    )}
                  </div>
                </div>
                )}

                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col flex-1 min-w-0">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                      Document checks
                    </h3>
                    <span className="text-xs font-semibold text-slate-400">
                      {activeDoc ? `${activeDoc.checks.length + 1} check${activeDoc.checks.length === 0 ? "" : "s"}` : ""}
                    </span>
                  </div>
                  {activeDoc ? (
                    <DocumentChecksPanel
                      checks={activeDoc.checks}
                      crossDocumentFindings={activeDocCrossFindings}
                      hasEnoughDocumentsForCrossCheck={documents.length >= 2}
                      signatureMatches={activeDocSignatureMatches}
                    />
                  ) : (
                    <p className="text-xs text-slate-400">Select a document to view its checks.</p>
                  )}
                </div>
              </section>
            </div>
          </>
        )}

        <ActivityTimeline entries={auditLog ?? []} isLoading={isAuditLoading} />
      </main>

      <footer className="mt-auto border-t border-slate-200 bg-white py-3 px-6 text-center text-xs text-slate-400">
        <div className="max-w-[1680px] mx-auto flex flex-col sm:flex-row justify-between items-center gap-2">
          <span>{APP_NAME} · {APP_FULL_NAME}</span>
        </div>
      </footer>

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && caseDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-2xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-rose-50 text-rose-600">
                <Trash2Icon className="size-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Delete Case</h3>
                <p className="text-xs text-slate-500 font-mono">{caseDetail.case_number}</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-3">
              Kya aap sure hain ki aap is case ko delete / close karna chahte hain?
            </p>

            <div className="rounded-xl border border-blue-200/80 bg-blue-50/60 p-3 text-xs text-blue-900 mb-5">
              <span className="font-semibold block mb-0.5">Audit History Preserved:</span>
              <p className="text-blue-800 text-[11.5px] leading-relaxed">
                Aapka case active lists se remove ho jayega, par iska audit trail, extracted records aur verification history system ke record mein hamesha safe rahegi.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => setIsDeleteModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-700 text-white shadow-xs transition"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2Icon className="size-3.5 animate-spin" />
                    <span>Deleting…</span>
                  </>
                ) : (
                  <span>Delete Case</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
