import * as React from "react"
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  ClockIcon,
  DownloadIcon,
  FileCheckIcon,
  FileTextIcon,
  PlusIcon,
  SearchIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserCheckIcon,
  UsersIcon,
} from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

import { listCases } from "@/api/cases"
import { getMyFamily } from "@/api/family"
import { ContradictionInsightBanner } from "@/components/dashboard/ContradictionInsightBanner"
import { DashboardMetricCard } from "@/components/dashboard/DashboardMetricCard"
import { useAuth } from "@/hooks/useAuth"
import { CASE_STATUS_LABELS, CASE_TYPE_LABELS, type CaseListItem } from "@/types/case"

interface CitizenDashboardProps {
  cases: CaseListItem[]
  isLoadingCases: boolean
}

export function CitizenDashboard({ cases, isLoadingCases }: CitizenDashboardProps) {
  const navigate = useNavigate()
  const { user, token } = useAuth()
  const [searchTerm, setSearchTerm] = React.useState("")
  const [statusFilter, setStatusFilter] = React.useState<"all" | "action_required" | "in_progress" | "cleared">("all")

  // Fetch Family Data
  const { data: family } = useQuery({
    queryKey: ["family", token],
    queryFn: () => getMyFamily("en", token as string),
    enabled: Boolean(token),
  })

  // Filter cases submitted by this citizen (or all cases in demo if none specifically matched)
  const myCases = React.useMemo(() => {
    const userOwned = cases.filter(
      (c) => !user?.id || c.submitted_by?.id === user.id || c.submitted_by?.email === user.email
    )
    return userOwned.length > 0 ? userOwned : cases
  }, [cases, user])

  // Computed metrics
  const totalCases = myCases.length
  const totalDocs = myCases.reduce((sum, c) => sum + (c.document_count || 1), 0)

  const clearedCases = myCases.filter(
    (c) => c.status === "auto_approved" || c.status === "approved" || c.status === "closed"
  )
  const inProgressCases = myCases.filter(
    (c) =>
      c.status === "submitted" ||
      c.status === "under_automated_review" ||
      c.status === "pending_manual_review" ||
      c.status === "under_investigation"
  )
  const actionRequiredCases = myCases.filter(
    (c) => c.status === "rejected" || c.flag?.flag === "high" || c.flag?.flag === "medium"
  )

  const verifiedDocsCount = clearedCases.reduce((sum, c) => sum + (c.document_count || 1), 0)
  const inProgressDocsCount = inProgressCases.reduce((sum, c) => sum + (c.document_count || 1), 0)

  // Overall Document Integrity Score (0-100)
  const integrityScore =
    totalCases > 0
      ? Math.round(
          ((clearedCases.length * 100 + inProgressCases.length * 75) / (totalCases * 100)) * 100
        )
      : 100

  // Filtered submissions list
  const filteredSubmissions = React.useMemo(() => {
    return myCases.filter((c) => {
      // Status filter
      if (statusFilter === "cleared") {
        const isCleared = c.status === "auto_approved" || c.status === "approved" || c.status === "closed"
        if (!isCleared) return false
      } else if (statusFilter === "in_progress") {
        const isInProgress =
          c.status === "submitted" ||
          c.status === "under_automated_review" ||
          c.status === "pending_manual_review" ||
          c.status === "under_investigation"
        if (!isInProgress) return false
      } else if (statusFilter === "action_required") {
        const isAction = c.status === "rejected" || c.flag?.flag === "high" || c.flag?.flag === "medium"
        if (!isAction) return false
      }

      // Search filter
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase()
        const matchesNum = c.case_number.toLowerCase().includes(q)
        const matchesType = (CASE_TYPE_LABELS[c.case_type] || c.case_type).toLowerCase().includes(q)
        return matchesNum || matchesType
      }

      return true
    })
  }, [myCases, statusFilter, searchTerm])

  const familyMembers = family?.members ?? []
  const familyHead = familyMembers.find((m) => m.is_head)

  return (
    <div className="space-y-6">
      {/* Hero Welcome Banner */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#0b1930] via-[#102244] to-[#1e3a8a] text-white p-6 sm:p-8 shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-200 text-xs font-semibold mb-3">
              <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Public Citizen & Applicant Portal</span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight">
              Namaste, {user?.full_name?.split(" ")[0] || "Citizen"}!
            </h1>
            <p className="text-sm sm:text-base text-slate-300 font-normal mt-2 leading-relaxed">
              Manage your verified documents, resolve cross-document contradictions across Indian identity proofs, and auto-fill official welfare and admission applications.
            </p>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 mt-6">
              <button
                type="button"
                onClick={() => navigate("/cases/new")}
                className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-full text-xs font-bold shadow-lg shadow-blue-600/30 transition-all hover:scale-[1.02]"
              >
                <PlusIcon className="size-4" />
                <span>Upload New Documents</span>
              </button>
              <button
                type="button"
                onClick={() => navigate("/family")}
                className="inline-flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white border border-white/20 px-4 py-2.5 rounded-full text-xs font-bold transition-colors"
              >
                <UsersIcon className="size-4" />
                <span>Manage Family ({familyMembers.length})</span>
              </button>
            </div>
          </div>

          {/* Document Integrity Health Score Widget */}
          <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-5 shrink-0 flex flex-col items-center justify-center text-center w-full md:w-64">
            <span className="text-[11px] font-bold uppercase tracking-wider text-blue-200">
              Document Readiness
            </span>
            <div className="text-4xl font-extrabold tracking-tight mt-1 text-white flex items-baseline gap-1">
              {integrityScore}%
              <span className="text-xs font-semibold text-emerald-400">
                {integrityScore >= 90 ? "Optimal" : "Needs Review"}
              </span>
            </div>
            <p className="text-[11px] text-slate-300 mt-1 max-w-[200px]">
              {actionRequiredCases.length === 0
                ? "No conflicting details found across your active uploads."
                : `${actionRequiredCases.length} case(s) contain conflicting records to verify.`}
            </p>
            <div className="w-full bg-white/20 rounded-full h-1.5 mt-3 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  integrityScore >= 90 ? "bg-emerald-400" : "bg-amber-400"
                }`}
                style={{ width: `${integrityScore}%` }}
              />
            </div>
          </div>
        </div>

        {/* Decorative backdrop shapes */}
        <div className="absolute -right-10 -bottom-10 size-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute right-40 -top-10 size-48 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
      </section>

      {/* 4 Metric Cards */}
      <section aria-label="Citizen Status Cards" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardMetricCard
          label="Verified Documents"
          value={verifiedDocsCount}
          sublabel={`across ${clearedCases.length} cleared case${clearedCases.length === 1 ? "" : "s"}`}
          icon={ShieldCheckIcon}
          color="emerald"
          progress={{ value: totalDocs > 0 ? (verifiedDocsCount / totalDocs) * 100 : 100 }}
          trend={{ direction: "up", label: "Tamper-free", positive: true }}
        />

        <DashboardMetricCard
          label="In Review / Analyzing"
          value={inProgressDocsCount}
          sublabel={`${inProgressCases.length} application${inProgressCases.length === 1 ? "" : "s"} processing`}
          icon={ClockIcon}
          color="blue"
          trend={{ direction: "neutral", label: "OCR & Anomaly Checks" }}
        />

        <DashboardMetricCard
          label="Contradictions Flagged"
          value={actionRequiredCases.length}
          sublabel={actionRequiredCases.length === 0 ? "Zero discrepancies" : "Needs re-upload / review"}
          icon={actionRequiredCases.length === 0 ? CheckCircle2Icon : AlertTriangleIcon}
          color={actionRequiredCases.length === 0 ? "slate" : "rose"}
          trend={
            actionRequiredCases.length > 0
              ? { direction: "down", label: "Attention required", positive: false }
              : { direction: "up", label: "100% matched", positive: true }
          }
        />

        <DashboardMetricCard
          label="Family Network"
          value={familyMembers.length}
          sublabel={familyHead ? `Head: ${familyHead.full_name}` : "Profile registered"}
          icon={UsersIcon}
          color="purple"
          onClick={() => navigate("/family")}
          badge="Linked Bundle"
        />
      </section>

      {/* Contradiction Engine Explanation */}
      <ContradictionInsightBanner />

      {/* 2-Column Main Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Submissions & Case Tracker */}
        <section className="lg:col-span-2 bg-white rounded-3xl border border-slate-200/90 p-5 sm:p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="text-base sm:text-lg font-extrabold text-[#0b1930] tracking-tight">
                  My Document Submissions
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Track the status of your uploaded document bundles and contradiction verdicts.
                </p>
              </div>

              <Link
                to="/my-cases"
                className="text-xs font-bold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1 group self-start sm:self-auto"
              >
                <span>View all ({totalCases})</span>
                <ArrowRightIcon className="size-3.5 transform group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>

            {/* Filter Pills & Search */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-1.5 overflow-x-auto py-1">
                {[
                  { id: "all", label: "All" },
                  { id: "action_required", label: "Action Required" },
                  { id: "in_progress", label: "In Review" },
                  { id: "cleared", label: "Cleared" },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setStatusFilter(t.id as any)}
                    className={`px-3 py-1.5 rounded-full text-xs font-bold shrink-0 transition-colors ${
                      statusFilter === t.id
                        ? "bg-[#0b1930] text-white"
                        : "bg-slate-100 hover:bg-slate-200 text-slate-600"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="relative">
                <SearchIcon className="size-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search case # or type..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-full w-full sm:w-48 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
            </div>

            {/* Submissions List */}
            <div className="mt-4 divide-y divide-slate-100">
              {isLoadingCases && (
                <div className="py-12 text-center text-xs text-slate-400">Loading your submissions...</div>
              )}

              {!isLoadingCases && filteredSubmissions.length === 0 && (
                <div className="py-12 text-center">
                  <FileTextIcon className="size-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No submissions found</p>
                  <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                    {searchTerm
                      ? "No records match your search filter."
                      : "You have not uploaded any document verification bundles yet."}
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate("/cases/new")}
                    className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold bg-[#0b1930] text-white hover:bg-blue-900 transition-colors"
                  >
                    <PlusIcon className="size-3.5" />
                    <span>Upload your first documents</span>
                  </button>
                </div>
              )}

              {!isLoadingCases &&
                filteredSubmissions.slice(0, 5).map((c) => {
                  const isCleared = c.status === "auto_approved" || c.status === "approved" || c.status === "closed"
                  const isAction = c.status === "rejected" || c.flag?.flag === "high"
                  const isInProgress = !isCleared && !isAction

                  return (
                    <div
                      key={c.id}
                      onClick={() => navigate(`/cases/${c.id}`)}
                      className="py-3.5 px-3 rounded-2xl hover:bg-slate-50/80 cursor-pointer transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className={`size-10 rounded-xl flex items-center justify-center shrink-0 ${
                            isCleared
                              ? "bg-emerald-100 text-emerald-700"
                              : isAction
                              ? "bg-rose-100 text-rose-700"
                              : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          <FileCheckIcon className="size-5" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-[#0b1930] hover:text-blue-600 transition-colors">
                              {c.case_number}
                            </span>
                            <span className="text-[11px] font-medium text-slate-500">
                              · {CASE_TYPE_LABELS[c.case_type] || c.case_type}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                            <span>{c.document_count} doc{c.document_count === 1 ? "" : "s"}</span>
                            <span>•</span>
                            <span>{new Date(c.created_at).toLocaleDateString()}</span>
                            {c.flag?.description && (
                              <>
                                <span>•</span>
                                <span className="truncate max-w-[200px] text-slate-600 font-medium">
                                  {c.flag.description}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${
                            isCleared
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : isAction
                              ? "bg-rose-50 text-rose-700 border-rose-200"
                              : "bg-blue-50 text-blue-700 border-blue-200"
                          }`}
                        >
                          <span
                            className={`size-1.5 rounded-full ${
                              isCleared ? "bg-emerald-500" : isAction ? "bg-rose-500" : "bg-blue-500 animate-pulse"
                            }`}
                          />
                          {CASE_STATUS_LABELS[c.status] || c.status}
                        </span>

                        <span className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg">
                          <ArrowRightIcon className="size-3.5" />
                        </span>
                      </div>
                    </div>
                  )
                })}
            </div>
          </div>

          {/* Bottom helper prompt */}
          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Showing recent submissions</span>
            <Link to="/cases/new" className="font-bold text-blue-600 hover:text-blue-700">
              + New upload
            </Link>
          </div>
        </section>

        {/* Right Column: Family Readiness & Form Auto-fill */}
        <div className="space-y-6">
          {/* Family Snapshot Card */}
          <section className="bg-white rounded-3xl border border-slate-200/90 p-5 sm:p-6 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <UsersIcon className="size-4 text-purple-600" />
                <h3 className="text-sm font-extrabold text-[#0b1930]">Family Readiness</h3>
              </div>
              <Link
                to="/family"
                className="text-xs font-bold text-blue-600 hover:text-blue-700 inline-flex items-center gap-0.5"
              >
                <span>Manage</span>
                <ArrowRightIcon className="size-3" />
              </Link>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Cross-member consistency checks for ration cards, address proofs & income certificates.
            </p>

            {familyMembers.length === 0 ? (
              <div className="p-4 rounded-2xl bg-purple-50/50 border border-purple-100 text-center">
                <UsersIcon className="size-6 text-purple-400 mx-auto mb-1.5" />
                <div className="text-xs font-bold text-purple-900">No family members registered</div>
                <p className="text-[11px] text-purple-700/80 mt-0.5">
                  Register members to detect cross-family document conflicts.
                </p>
                <button
                  type="button"
                  onClick={() => navigate("/family")}
                  className="mt-3 px-3 py-1.5 rounded-lg text-xs font-bold bg-purple-600 text-white hover:bg-purple-700 transition-colors"
                >
                  Set up family bundle
                </button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {familyMembers.slice(0, 4).map((m) => (
                  <div
                    key={m.id}
                    onClick={() => navigate("/family")}
                    className="p-3 rounded-xl bg-slate-50/80 hover:bg-slate-100/80 cursor-pointer transition-colors flex items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-[#0b1930] truncate">{m.full_name}</div>
                      <div className="text-[11px] text-slate-500 capitalize">
                        {m.relation_label || m.relation} {m.is_head && "· Family Head"}
                      </div>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                        m.profile_ready
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-slate-200 text-slate-700"
                      }`}
                    >
                      {m.profile_ready ? "Verified" : "Pending Docs"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Official Form Auto-Fill CTA Card */}
          <section className="bg-gradient-to-br from-blue-50 to-indigo-50/70 rounded-3xl border border-blue-200/80 p-5 sm:p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <SparklesIcon className="size-4 text-blue-600" />
              <h3 className="text-sm font-extrabold text-[#0b1930]">Official Form Auto-Fill</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Use verified data from your document bundle to automatically fill government welfare, scholarship, and employment forms without typos.
            </p>

            <div className="mt-4 pt-3 border-t border-blue-100/80 flex items-center justify-between">
              <span className="text-[11px] font-semibold text-blue-900">
                {totalCases > 0 ? "Ready from verified profile" : "Upload documents to enable"}
              </span>
              <button
                type="button"
                onClick={() => {
                  if (myCases.length > 0) {
                    navigate(`/cases/${myCases[0].id}`)
                  } else {
                    navigate("/cases/new")
                  }
                }}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-700 hover:text-blue-800"
              >
                <span>{myCases.length > 0 ? "Select form" : "Start now"}</span>
                <ArrowRightIcon className="size-3" />
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
