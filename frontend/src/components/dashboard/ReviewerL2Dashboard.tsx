import * as React from "react"
import {
  AlertOctagonIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  FileSearchIcon,
  FlameIcon,
  LayersIcon,
  SearchIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  SlidersIcon,
} from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

import { listIssuers, listRiskRules } from "@/api/settings"
import { CaseFlagBadge } from "@/components/case/CaseBadges"
import { DashboardMetricCard } from "@/components/dashboard/DashboardMetricCard"
import { useAuth } from "@/hooks/useAuth"
import { CASE_STATUS_LABELS, CASE_TYPE_LABELS, type CaseListItem } from "@/types/case"

interface ReviewerL2DashboardProps {
  cases: CaseListItem[]
  isLoadingCases: boolean
}

export function ReviewerL2Dashboard({ cases, isLoadingCases }: ReviewerL2DashboardProps) {
  const navigate = useNavigate()
  const { token } = useAuth()
  const [search, setSearch] = React.useState("")

  // Fetch Risk Rules & Issuers for Senior Reviewer telemetry
  const { data: rules } = useQuery({
    queryKey: ["riskRules", token],
    queryFn: () => listRiskRules(token as string),
    enabled: Boolean(token),
  })

  const { data: issuers } = useQuery({
    queryKey: ["issuers", token],
    queryFn: () => listIssuers(token as string),
    enabled: Boolean(token),
  })

  const activeRulesCount = rules?.filter((r) => r.is_active).length ?? 7
  const issuersCount = issuers?.length ?? 12

  const isOpen = (c: CaseListItem) =>
    c.status !== "approved" && c.status !== "rejected" && c.status !== "closed"

  // Escalated cases (assigned_tier === "l2")
  const escalatedCases = cases.filter((c) => c.assigned_tier === "l2" && isOpen(c))
  const highRiskCount = cases.filter((c) => c.flag?.flag === "high").length
  const forensicFlagsCount = cases.filter(
    (c) =>
      c.flag?.description?.toLowerCase().includes("tamper") ||
      c.flag?.description?.toLowerCase().includes("signature") ||
      c.flag?.description?.toLowerCase().includes("metadata") ||
      c.flag?.flag === "high"
  ).length

  const filteredEscalations = React.useMemo(() => {
    return escalatedCases.filter((c) => {
      if (search.trim()) {
        const q = search.toLowerCase()
        return (
          c.case_number.toLowerCase().includes(q) ||
          (c.flag?.description && c.flag.description.toLowerCase().includes(q))
        )
      }
      return true
    })
  }, [escalatedCases, search])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold tracking-widest uppercase text-amber-600">
              Senior Risk & Escalations Center
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
              <ShieldAlertIcon className="size-3 text-amber-600" />
              Level 2 Authority
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-[#0b1930] tracking-tight mt-1">
            Escalation & Compliance Console
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 font-normal mt-1.5 max-w-2xl">
            High-severity conflict adjudication, document forensic verification, and risk scoring rule adjustments.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => navigate("/settings/risk-rules")}
            className="inline-flex items-center gap-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-800 px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all shadow-2xs"
          >
            <SlidersIcon className="size-3.5 text-blue-600" />
            <span>Risk Rules</span>
          </button>
          <button
            type="button"
            onClick={() => navigate("/settings/issuer-registry")}
            className="inline-flex items-center gap-2 bg-[#0b1930] hover:bg-[#13233f] text-white px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all shadow-sm"
          >
            <DatabaseIcon className="size-3.5" />
            <span>Issuer Registry</span>
          </button>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <section aria-label="L2 Metrics" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardMetricCard
          label="Active L2 Escalations"
          value={escalatedCases.length}
          sublabel="Pending senior risk determination"
          icon={FlameIcon}
          color={escalatedCases.length > 0 ? "purple" : "slate"}
          badge="High Priority"
          trend={{ direction: escalatedCases.length > 0 ? "down" : "neutral", label: "Requires sign-off", positive: false }}
        />

        <DashboardMetricCard
          label="High-Severity Flags"
          value={highRiskCount}
          sublabel="Score > 70 across the organization"
          icon={AlertOctagonIcon}
          color="rose"
        />

        <DashboardMetricCard
          label="Forensic / Tamper Flags"
          value={forensicFlagsCount}
          sublabel="ELA, metadata or signature alerts"
          icon={FileSearchIcon}
          color="amber"
        />

        <DashboardMetricCard
          label="Active Risk Rules"
          value={activeRulesCount}
          sublabel={`${issuersCount} verified issuers in registry`}
          icon={SlidersIcon}
          color="blue"
          onClick={() => navigate("/settings/risk-rules")}
        />
      </section>

      {/* 2-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Escalations Queue */}
        <section className="lg:col-span-7 bg-white rounded-3xl p-5 sm:p-6 border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="text-base sm:text-lg font-extrabold text-[#0b1930] tracking-tight">
                  Escalated Cases for Determination
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Referred by Reviewer L1 or triggered by automated anomaly thresholds.
                </p>
              </div>

              <div className="relative">
                <SearchIcon className="size-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter case..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-full w-full sm:w-44 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                />
              </div>
            </div>

            {/* List */}
            <div className="divide-y divide-slate-100">
              {isLoadingCases && (
                <div className="py-12 text-center text-xs text-slate-400">Loading escalations...</div>
              )}

              {!isLoadingCases && filteredEscalations.length === 0 && (
                <div className="py-12 text-center">
                  <CheckCircle2Icon className="size-8 text-emerald-400 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No pending L2 escalations</p>
                  <p className="text-xs text-slate-400 mt-1">
                    All escalated cases have been reviewed or no active cases require L2 intervention.
                  </p>
                </div>
              )}

              {!isLoadingCases &&
                filteredEscalations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/cases/${c.id}`)}
                    className="py-3.5 px-3 rounded-2xl hover:bg-amber-50/50 cursor-pointer transition-colors flex items-center justify-between gap-3 group"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#0b1930] group-hover:text-blue-600 transition-colors">
                          {c.case_number}
                        </span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 uppercase">
                          Tier L2
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 truncate">
                        {c.document_count} doc{c.document_count === 1 ? "" : "s"} · {CASE_TYPE_LABELS[c.case_type] || c.case_type}
                      </div>
                      {c.flag?.description && (
                        <div className="text-[11px] font-medium text-amber-800 mt-1 flex items-center gap-1">
                          <span>Reason:</span>
                          <span className="truncate">{c.flag.description}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {c.flag && <CaseFlagBadge flag={c.flag} />}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/cases/${c.id}`)
                        }}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#0b1930] hover:bg-amber-700 text-white transition-colors"
                      >
                        <span>Adjudicate</span>
                        <ArrowRightIcon className="size-3" />
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Senior Determinations Logged to Audit Trail</span>
            <Link to="/audit-history" className="font-bold text-amber-700 hover:text-amber-800">
              Audit History →
            </Link>
          </div>
        </section>

        {/* Right Column (5 cols): Forensic Checks & Rule Overview */}
        <div className="lg:col-span-5 space-y-6">
          {/* Forensic Checks Radar */}
          <section className="bg-white rounded-3xl p-5 sm:p-6 border border-slate-200/90 shadow-sm">
            <h2 className="text-base font-extrabold text-[#0b1930] tracking-tight">
              Forensic Anomaly Suite
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Automated pixel and metadata integrity checks running on all PDF & image uploads.
            </p>

            <div className="mt-4 space-y-3 text-xs">
              {[
                { title: "Error Level Analysis (ELA)", desc: "Detects recompression anomalies and spliced image text.", status: "Active" },
                { title: "PDF Structure & Incremental Saves", desc: "Flags modified post-signing objects and hidden revisions.", status: "Active" },
                { title: "Copy-Move Forgery Detection", desc: "OpenCV feature matching for cloned document regions.", status: "Active" },
                { title: "Perceptual Image Hashing", desc: "Catches duplicate or near-duplicate documents across cases.", status: "Active" },
              ].map((f) => (
                <div key={f.title} className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-start justify-between gap-2">
                  <div>
                    <div className="font-bold text-slate-800">{f.title}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{f.desc}</div>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 shrink-0">
                    {f.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Quick Config Links */}
          <section className="bg-gradient-to-br from-slate-900 to-[#0b1930] text-white rounded-3xl p-5 sm:p-6 shadow-md">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Governance Controls
              </h3>
              <ShieldCheckIcon className="size-4 text-emerald-400" />
            </div>
            <p className="text-xs text-slate-300 mb-4">
              Tune automated severity thresholds and manage approved institution credentials.
            </p>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => navigate("/settings/risk-rules")}
                className="p-3 rounded-xl bg-white/10 hover:bg-white/20 text-left transition-colors font-semibold"
              >
                <div>Risk Scoring</div>
                <div className="text-[10px] text-slate-300 font-normal mt-0.5">Weights & Tiers</div>
              </button>
              <button
                type="button"
                onClick={() => navigate("/settings/issuer-registry")}
                className="p-3 rounded-xl bg-white/10 hover:bg-white/20 text-left transition-colors font-semibold"
              >
                <div>Issuers</div>
                <div className="text-[10px] text-slate-300 font-normal mt-0.5">Fuzzy Registry</div>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
