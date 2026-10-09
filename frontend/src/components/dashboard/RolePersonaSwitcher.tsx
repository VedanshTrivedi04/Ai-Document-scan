import type * as React from "react"
import {
  RotateCcwIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TerminalIcon,
  UserCheckIcon,
} from "lucide-react"

import type { UserRole } from "@/types/auth"

export type PersonaRole = "user" | "reviewer_l1" | "reviewer_l2" | "platform_admin"

export interface RolePersonaSwitcherProps {
  currentPersona: PersonaRole
  onPersonaChange: (persona: PersonaRole) => void
  actualRole?: UserRole
}

const PERSONAS: {
  role: PersonaRole
  title: string
  subtitle: string
  badge: string
  icon: React.ComponentType<{ className?: string }>
  color: string
}[] = [
  {
    role: "user",
    title: "Citizen / Applicant",
    subtitle: "Document Vault & Family",
    badge: "Public User",
    icon: UserCheckIcon,
    color: "from-blue-600 to-indigo-600",
  },
  {
    role: "reviewer_l1",
    title: "Reviewer L1",
    subtitle: "Triage & Queue Operations",
    badge: "First-Line Review",
    icon: ShieldCheckIcon,
    color: "from-emerald-600 to-teal-600",
  },
  {
    role: "reviewer_l2",
    title: "Reviewer L2",
    subtitle: "Escalations & Risk Governance",
    badge: "Senior Risk Officer",
    icon: ShieldAlertIcon,
    color: "from-amber-600 to-orange-600",
  },
  {
    role: "platform_admin",
    title: "Platform Admin",
    subtitle: "Multi-tenant & Infrastructure",
    badge: "Super Admin",
    icon: TerminalIcon,
    color: "from-purple-600 to-slate-800",
  },
]

export function RolePersonaSwitcher({
  currentPersona,
  onPersonaChange,
  actualRole = "user",
}: RolePersonaSwitcherProps) {
  const isCustomView = currentPersona !== actualRole

  return (
    <div className="bg-white/80 backdrop-blur-md rounded-2xl border border-slate-200/90 p-3 sm:p-4 shadow-sm">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        {/* Header note with icon */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="size-8 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white shrink-0 shadow-sm shadow-blue-500/20">
            <SparklesIcon className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold text-[#0b1930] tracking-tight">
                Role-Adaptive Dashboard
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/60">
                Live View
              </span>
              {isCustomView && (
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200/60 animate-pulse">
                  Previewing Different Role
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500 truncate mt-0.5">
              Switch persona to explore the tailored experience for each user type.
            </p>
          </div>
        </div>

        {/* Action reset if in preview */}
        {isCustomView && (
          <button
            type="button"
            onClick={() => onPersonaChange(actualRole as PersonaRole)}
            className="self-start lg:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
          >
            <RotateCcwIcon className="size-3" />
            <span>Reset to My Role ({actualRole})</span>
          </button>
        )}
      </div>

      {/* Persona Pill Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 pt-3 border-t border-slate-100">
        {PERSONAS.map((p) => {
          const isActive = currentPersona === p.role
          const Icon = p.icon
          const isUserActual = actualRole === p.role

          return (
            <button
              key={p.role}
              type="button"
              onClick={() => onPersonaChange(p.role)}
              className={`relative text-left p-2.5 sm:p-3 rounded-xl border transition-all duration-200 flex flex-col justify-between ${
                isActive
                  ? "bg-[#0b1930] text-white border-[#0b1930] shadow-md shadow-slate-900/10 scale-[1.01]"
                  : "bg-white hover:bg-slate-50/90 text-slate-800 border-slate-200/80 hover:border-slate-300"
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span
                  className={`p-1.5 rounded-lg ${
                    isActive ? "bg-white/10 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  <Icon className="size-3.5" />
                </span>
                {isUserActual && (
                  <span
                    className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                      isActive ? "bg-blue-500/30 text-blue-200" : "bg-blue-50 text-blue-600"
                    }`}
                  >
                    Your Role
                  </span>
                )}
              </div>
              <div>
                <div
                  className={`text-xs font-bold leading-tight ${
                    isActive ? "text-white" : "text-[#0b1930]"
                  }`}
                >
                  {p.title}
                </div>
                <div
                  className={`text-[10px] font-medium leading-normal mt-0.5 ${
                    isActive ? "text-slate-300" : "text-slate-400"
                  }`}
                >
                  {p.subtitle}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
