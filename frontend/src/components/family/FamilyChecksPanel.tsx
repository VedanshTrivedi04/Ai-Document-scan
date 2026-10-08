import {
  AlertCircleIcon,
  AlertTriangleIcon,
  CheckCircle2Icon,
  HelpCircleIcon,
  ShieldCheckIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type { FamilyCheck, FamilyCheckCounts, FamilyCheckSeverity } from "@/types/family"

interface FamilyChecksPanelProps {
  checks: FamilyCheck[]
  checkCounts: FamilyCheckCounts
  currentLang?: string
}

const CHECKS_I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Household verification checks",
    subtitle: "Automated checks cross-referencing identity, shared address, parent names, and birth order.",
    matched: "matched",
    conflict: "conflict",
    conflicts: "conflicts",
    not_checked: "not checked",
    match_status: "Match",
    conflict_status: "Conflict",
    not_checked_status: "Not checked",
    no_checks: "No household checks computed yet.",
  },
  hi: {
    title: "पारिवारिक सत्यापन जाँच",
    subtitle: "पहचान, साझा पता, माता-पिता के नाम और जन्म क्रम की स्वचालित क्रॉस-जाँच।",
    matched: "सत्यापित",
    conflict: "विरोधाभास",
    conflicts: "विरोधाभास",
    not_checked: "जाँच नहीं हुई",
    match_status: "सत्यापित",
    conflict_status: "विरोधाभास",
    not_checked_status: "जाँच नहीं हुई",
    no_checks: "अभी तक कोई पारिवारिक जाँच नहीं हुई है।",
  },
}

const SEVERITY_BADGES: Record<FamilyCheckSeverity, { label: string; className: string }> = {
  critical: { label: "Critical", className: "bg-red-600 text-white" },
  high: { label: "High", className: "bg-red-100 text-red-800 border-red-300" },
  medium: { label: "Medium", className: "bg-amber-100 text-amber-800 border-amber-300" },
  low: { label: "Low", className: "bg-yellow-100 text-yellow-800 border-yellow-300" },
  info: { label: "Info", className: "bg-blue-100 text-blue-800 border-blue-300" },
}

export function FamilyChecksPanel({
  checks,
  checkCounts,
  currentLang = "en",
}: FamilyChecksPanelProps) {
  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = CHECKS_I18N[langKey] ?? CHECKS_I18N.en

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pb-3.5 border-b border-border/80">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="size-4.5 text-primary" />
            <h3 className="text-sm font-bold text-foreground">{t.title}</h3>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">{t.subtitle}</p>
        </div>

        {/* Counts summary chips */}
        <div className="flex items-center gap-1.5 flex-wrap text-xs">
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2Icon className="size-3 text-emerald-600" />
            {checkCounts.match} {t.matched}
          </span>
          {checkCounts.conflict > 0 && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-800 border border-red-200">
              <AlertTriangleIcon className="size-3 text-red-600" />
              {checkCounts.conflict} {checkCounts.conflict === 1 ? t.conflict : t.conflicts}
            </span>
          )}
          {checkCounts.not_checked > 0 && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted/60 text-muted-foreground border border-border/80">
              <HelpCircleIcon className="size-3 text-muted-foreground" />
              {checkCounts.not_checked} {t.not_checked}
            </span>
          )}
        </div>
      </div>

      {/* Checks list */}
      {checks.length === 0 ? (
        <p className="text-xs text-muted-foreground italic py-2">{t.no_checks}</p>
      ) : (
        <div className="divide-y divide-border/60">
          {checks.map((check, idx) => {
            const isMatch = check.result === "match"
            const isConflict = check.result === "conflict"
            const isNotChecked = check.result === "not_checked"

            const sevInfo = SEVERITY_BADGES[check.severity] ?? SEVERITY_BADGES.info

            return (
              <div key={idx} className="py-3 flex flex-col gap-1.5 text-xs">
                {/* Top line: Label + Member & Result Pill */}
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-foreground text-xs">{check.label}</span>
                    <span className="text-[11px] text-muted-foreground font-medium">
                      ({check.member_name})
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {isMatch && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        <CheckCircle2Icon className="size-3 text-emerald-600" />
                        {t.match_status}
                      </span>
                    )}

                    {isConflict && (
                      <div className="flex items-center gap-1">
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-full border border-red-200">
                          <AlertCircleIcon className="size-3 text-red-600" />
                          {t.conflict_status}
                        </span>
                        <span
                          className={cn(
                            "px-1.5 py-0.2 rounded text-[10px] font-bold border",
                            sevInfo.className
                          )}
                        >
                          {sevInfo.label}
                        </span>
                      </div>
                    )}

                    {isNotChecked && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted/40 px-2 py-0.5 rounded-full border border-border/80">
                        <HelpCircleIcon className="size-3 text-muted-foreground" />
                        {t.not_checked_status}
                      </span>
                    )}
                  </div>
                </div>

                {/* Summary sentence */}
                <p
                  className={cn(
                    "text-xs leading-relaxed",
                    isConflict
                      ? "text-red-900 bg-red-50/60 p-2 rounded-lg border border-red-200/60 font-medium"
                      : isMatch
                      ? "text-emerald-950 font-normal"
                      : "text-muted-foreground italic"
                  )}
                >
                  {check.summary}
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
