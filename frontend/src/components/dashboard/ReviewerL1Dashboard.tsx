import * as React from "react"
import {
  ArrowRightIcon,
  CheckCircle2Icon,
  ClockIcon,
  FileCheckIcon,
  FileTextIcon,
  FlameIcon,
  LayersIcon,
  SearchIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UploadCloudIcon,
} from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { CaseFlagBadge } from "@/components/case/CaseBadges"
import { ContradictionInsightBanner } from "@/components/dashboard/ContradictionInsightBanner"
import { DashboardMetricCard } from "@/components/dashboard/DashboardMetricCard"
import { CASE_STATUS_LABELS, CASE_TYPE_LABELS, type CaseListItem } from "@/types/case"

interface ReviewerL1DashboardProps {
  cases: CaseListItem[]
  isLoadingCases: boolean
}

export function ReviewerL1Dashboard({ cases, isLoadingCases }: ReviewerL1DashboardProps) {
  const navigate = useNavigate()
  const [tierFilter, setTierFilter] = React.useState<"all" | "high" | "medium" | "low" | "escalated">("all")
  const [search, setSearch] = React.useState("")

  const totalCases = cases.length
  const documentsInQueue = cases.reduce((acc, c) => acc + (c.document_count || 1), 0)
  const isOpen = (c: CaseListItem) =>
    c.status !== "approved" && c.status !== "rejected" && c.status !== "closed"

  const highRiskCount = cases.filter((c) => c.flag?.flag === "high").length
  const mediumRiskCount = cases.filter((c) => c.flag?.flag === "medium").length
  const lowRiskCount = cases.filter((c) => c.flag?.flag === "low").length
  const pendingCount = cases.filter((c) => c.flag?.flag === "pending").length
  const escalatedCount = cases.filter((c) => c.assigned_tier === "l2" && isOpen(c)).length
  const clearedCount = cases.filter(
    (c) => c.status === "auto_approved" || c.status === "approved" || c.status === "closed"
  ).length

  // Filtered queue items
  const priorityQueue = React.useMemo(() => {
    return cases
      .filter((c) => {
        if (!isOpen(c)) return false
        if (tierFilter === "high" && c.flag?.flag !== "high") return false
        if (tierFilter === "medium" && c.flag?.flag !== "medium") return false
        if (tierFilter === "low" && c.flag?.flag !== "low") return false
        if (tierFilter === "escalated" && c.assigned_tier !== "l2") return false

        if (search.trim()) {
          const q = search.toLowerCase()
          return (
            c.case_number.toLowerCase().includes(q) ||
            (c.submitted_by?.email && c.submitted_by.email.toLowerCase().includes(q))
          )
        }
        return true
      })
      .sort((a, b) => {
        const esc = Number(b.assigned_tier === "l2") - Number(a.assigned_tier === "l2")
        if (esc !== 0) return esc
        const scoreDiff = (b.flag?.score ?? -1) - (a.flag?.score ?? -1)
        if (scoreDiff !== 0) return scoreDiff
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      })
  }, [cases, tierFilter, search])

  return (
    <div className="space-y-6">
      {/* Page Title & Live Status */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold tracking-widest uppercase text-blue-600">
              Operational Reviewer Console
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Triage SLA &lt; 4h
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-[#0b1930] tracking-tight mt-1">
            Verification & Review Queue
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 font-normal mt-1.5 max-w-2xl">
            First-line case evaluation, AI anomaly verification, and escalated dispute triage.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => navigate("/cases")}
            className="inline-flex items-center gap-2 bg-[#0b1930] hover:bg-[#13233f] text-white px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all shadow-sm"
          >
            <LayersIcon className="size-3.5" />
            <span>Open Full Queue</span>
          </button>
          <button
            type="button"
            onClick={() => navigate("/cases/new")}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all shadow-sm"
          >
            <UploadCloudIcon className="size-3.5" />
            <span>New Intake</span>
          </button>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <section aria-label="Reviewer KPIs" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardMetricCard
          label="Documents in Queue"
          value={documentsInQueue}
          sublabel={`across ${totalCases} total case${totalCases === 1 ? "" : "s"}`}
          icon={ClockIcon}
          color="blue"
          trend={{ direction: "neutral", label: "Real-time sync" }}
        />

        <DashboardMetricCard
          label="High-Risk Flagged"
          value={highRiskCount}
          sublabel={`${mediumRiskCount} cases at medium risk tier`}
          icon={ShieldAlertIcon}
          color={highRiskCount > 0 ? "rose" : "slate"}
          trend={{ direction: highRiskCount > 0 ? "down" : "neutral", label: "Requires triage", positive: false }}
        />

        <DashboardMetricCard
          label="Cleared & Approved"
          value={clearedCount}
          sublabel="Resolved by automation or L1"
          icon={ShieldCheckIcon}
          color="emerald"
          trend={{ direction: "up", label: "Clean verified", positive: true }}
        />

        <DashboardMetricCard
          label="Escalated to L2"
          value={escalatedCount}
          sublabel="Handed off to Senior Risk Officer"
          icon={FlameIcon}
          color="purple"
          badge="L2 Review"
        />
      </section>

      {/* Contradiction Banner */}
      <ContradictionInsightBanner />

      {/* 2-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 cols): Risk Tier Distribution & Top Signals */}
        <div className="lg:col-span-5 space-y-6">
          <section className="bg-white rounded-3xl p-5 sm:p-6 border border-slate-200/90 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-extrabold text-[#0b1930] tracking-tight">
                  Risk Tier Distribution
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Explainable anomaly score (0–100) from weighted rules.
                </p>
              </div>
              <span className="text-[10px] font-bold tracking-wider text-slate-500 border border-slate-200 bg-slate-50 px-2 py-0.5 rounded-full uppercase">
                {totalCases} cases
              </span>
            </div>

            {/* Distribution Bars */}
            <div className="mt-5 space-y-4">
              {[
                { label: "High Risk (70–100)", count: highRiskCount, barClass: "bg-rose-500", textClass: "text-rose-600", filter: "high" },
                { label: "Medium Risk (40–69)", count: mediumRiskCount, barClass: "bg-amber-500", textClass: "text-amber-600", filter: "medium" },
                { label: "Low Risk (0–39)", count: lowRiskCount, barClass: "bg-emerald-500", textClass: "text-emerald-600", filter: "low" },
                { label: "Analyzing / In-flight", count: pendingCount, barClass: "bg-slate-300", textClass: "text-slate-500", filter: "all" },
              ].map((row) => {
                const pct = totalCases > 0 ? Math.round((row.count / totalCases) * 100) : 0
                return (
                  <div
                    key={row.label}
                    onClick={() => setTierFilter(row.filter as any)}
                    className="p-2.5 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <div className="flex justify-between text-xs font-semibold mb-1.5">
                      <span className="text-slate-700">{row.label}</span>
                      <span className={`${row.textClass} font-bold`}>
                        {row.count} ({pct}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`${row.barClass} h-full rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100">
              <div className="bg-blue-50/70 border border-blue-200/60 rounded-xl p-3.5 text-xs text-slate-700 leading-relaxed">
                <span className="font-bold text-blue-800">Top Anomaly Signals:</span> Cross-document date mismatches, unregistered vendor letterheads, and incremental PDF save variations.
              </div>
            </div>
          </section>

          {/* Quick Shortcuts */}
          <section className="bg-slate-900 text-white rounded-3xl p-5 sm:p-6 shadow-md">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-2">
              Reviewer Actions
            </h3>
            <div className="space-y-2 text-xs">
              <button
                type="button"
                onClick={() => navigate("/cases/bulk")}
                className="w-full p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-left flex items-center justify-between transition-colors"
              >
                <span>Bulk Document Processing</span>
                <ArrowRightIcon className="size-3.5 text-slate-400" />
              </button>
              <button
                type="button"
                onClick={() => navigate("/audit-history")}
                className="w-full p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-left flex items-center justify-between transition-colors"
              >
                <span>Inspect Audit Log</span>
                <ArrowRightIcon className="size-3.5 text-slate-400" />
              </button>
            </div>
          </section>
        </div>

        {/* Right Column (7 cols): Priority Review Queue */}
        <section className="lg:col-span-7 bg-white rounded-3xl p-5 sm:p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="text-base sm:text-lg font-extrabold text-[#0b1930] tracking-tight">
                  Priority Review Queue
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Mismatches and high-risk cases prioritized first.
                </p>
              </div>

              <Link
                to="/cases"
                className="text-xs font-bold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1 group self-start sm:self-auto"
              >
                <span>View all in queue</span>
                <ArrowRightIcon className="size-3.5 transform group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>

            {/* Filter Pills + Search */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-1.5 overflow-x-auto py-1">
                {[
                  { id: "all", label: "All Open" },
                  { id: "high", label: "High Risk" },
                  { id: "medium", label: "Medium Risk" },
                  { id: "escalated", label: "Escalated" },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTierFilter(t.id as any)}
                    className={`px-3 py-1.5 rounded-full text-xs font-bold shrink-0 transition-colors ${
                      tierFilter === t.id
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
                  placeholder="Filter case #..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-full w-full sm:w-44 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
            </div>

            {/* Queue List */}
            <div className="mt-4 divide-y divide-slate-100">
              {isLoadingCases && (
                <div className="py-12 text-center text-xs text-slate-400">Loading cases...</div>
              )}

              {!isLoadingCases && priorityQueue.length === 0 && (
                <div className="py-12 text-center">
                  <CheckCircle2Icon className="size-8 text-emerald-400 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">Queue is clear</p>
                  <p className="text-xs text-slate-400 mt-1">No open cases matching your current filter.</p>
                </div>
              )}

              {!isLoadingCases &&
                priorityQueue.slice(0, 6).map((c) => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/cases/${c.id}`)}
                    className="py-3 px-3 rounded-2xl hover:bg-slate-50 cursor-pointer transition-colors flex items-center justify-between gap-3 group"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#0b1930] group-hover:text-blue-600 transition-colors">
                          {c.case_number}
                        </span>
                        {c.assigned_tier === "l2" && (
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 uppercase">
                            L2
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 truncate">
                        {c.document_count} doc{c.document_count === 1 ? "" : "s"} · {CASE_TYPE_LABELS[c.case_type] || c.case_type} · {CASE_STATUS_LABELS[c.status]}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {c.flag && <CaseFlagBadge flag={c.flag} />}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/cases/${c.id}`)
                        }}
                        className="hidden sm:inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#0b1930] hover:bg-blue-600 text-white transition-colors"
                      >
                        <span>Review</span>
                        <ArrowRightIcon className="size-3" />
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Showing top prioritized items</span>
            <Link to="/cases" className="font-bold text-blue-600 hover:text-blue-700">
              Open Full Queue →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
