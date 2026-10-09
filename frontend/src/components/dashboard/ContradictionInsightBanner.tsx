import * as React from "react"
import { CheckCircle2Icon, ChevronDownIcon, ChevronUpIcon, InfoIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react"

export function ContradictionInsightBanner() {
  const [expanded, setExpanded] = React.useState(false)

  return (
    <div className="rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/90 via-indigo-50/60 to-white p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="size-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-sm shadow-blue-500/30">
            <SparklesIcon className="size-4" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xs sm:text-sm font-bold text-[#0b1930]">
                Smart Contradiction Engine Active
              </h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                13 Indian Languages Supported
              </span>
            </div>
            <p className="text-xs text-slate-600 mt-0.5">
              Phonetic matching tolerates regional spelling and transliteration variants, while isolating real identity and income conflicts.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shrink-0 shadow-2xs"
        >
          <span>{expanded ? "Hide Details" : "How it Works"}</span>
          {expanded ? <ChevronUpIcon className="size-3.5" /> : <ChevronDownIcon className="size-3.5" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-blue-100 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="bg-white/80 rounded-xl p-3 border border-emerald-100">
            <div className="flex items-center gap-1.5 font-bold text-emerald-800 mb-1">
              <CheckCircle2Icon className="size-3.5 text-emerald-600" />
              <span>Harmless Variations Ignored</span>
            </div>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Accepts phonetic differences across scripts (e.g. <em>Mohd.</em> vs <em>Mohammad</em>, <em>Laxmi</em> vs <em>Lakshmi</em>, or differing address pincode formatting) without blocking applications.
            </p>
          </div>

          <div className="bg-white/80 rounded-xl p-3 border border-amber-100">
            <div className="flex items-center gap-1.5 font-bold text-amber-800 mb-1">
              <ShieldCheckIcon className="size-3.5 text-amber-600" />
              <span>Real Conflicts Flagged</span>
            </div>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Detects genuine conflicts with pinpoint source locations — e.g. conflicting Father's Name across Aadhaar and Marksheet, altered DOB, or inconsistent family income declarations.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
