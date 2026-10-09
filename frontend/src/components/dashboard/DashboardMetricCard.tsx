import type * as React from "react"
import { TrendingDownIcon, TrendingUpIcon } from "lucide-react"

export interface DashboardMetricCardProps {
  label: string
  value: React.ReactNode
  sublabel?: React.ReactNode
  icon: React.ComponentType<{ className?: string }>
  color?: "blue" | "emerald" | "amber" | "rose" | "purple" | "slate"
  trend?: {
    direction: "up" | "down" | "neutral"
    label: string
    positive?: boolean
  }
  progress?: {
    value: number // 0-100
    color?: string
  }
  onClick?: () => void
  badge?: string
}

const COLOR_STYLES = {
  blue: {
    bg: "bg-gradient-to-br from-white to-blue-50/50",
    border: "border-blue-200/80 hover:border-blue-400/80",
    iconBg: "bg-blue-600 text-white shadow-md shadow-blue-500/20",
    accentText: "text-blue-600",
    glow: "hover:shadow-[0_8px_30px_rgb(37,99,235,0.12)]",
    barColor: "bg-blue-600",
  },
  emerald: {
    bg: "bg-gradient-to-br from-white to-emerald-50/50",
    border: "border-emerald-200/80 hover:border-emerald-400/80",
    iconBg: "bg-emerald-600 text-white shadow-md shadow-emerald-500/20",
    accentText: "text-emerald-600",
    glow: "hover:shadow-[0_8px_30px_rgb(5,150,105,0.12)]",
    barColor: "bg-emerald-600",
  },
  amber: {
    bg: "bg-gradient-to-br from-white to-amber-50/50",
    border: "border-amber-200/80 hover:border-amber-400/80",
    iconBg: "bg-amber-500 text-white shadow-md shadow-amber-500/20",
    accentText: "text-amber-600",
    glow: "hover:shadow-[0_8px_30px_rgb(217,119,6,0.12)]",
    barColor: "bg-amber-500",
  },
  rose: {
    bg: "bg-gradient-to-br from-white to-rose-50/50",
    border: "border-rose-200/80 hover:border-rose-400/80",
    iconBg: "bg-rose-600 text-white shadow-md shadow-rose-500/20",
    accentText: "text-rose-600",
    glow: "hover:shadow-[0_8px_30px_rgb(225,29,72,0.12)]",
    barColor: "bg-rose-600",
  },
  purple: {
    bg: "bg-gradient-to-br from-white to-purple-50/50",
    border: "border-purple-200/80 hover:border-purple-400/80",
    iconBg: "bg-purple-600 text-white shadow-md shadow-purple-500/20",
    accentText: "text-purple-600",
    glow: "hover:shadow-[0_8px_30px_rgb(147,51,234,0.12)]",
    barColor: "bg-purple-600",
  },
  slate: {
    bg: "bg-gradient-to-br from-white to-slate-50/50",
    border: "border-slate-200 hover:border-slate-300",
    iconBg: "bg-slate-700 text-white shadow-md shadow-slate-500/20",
    accentText: "text-slate-700",
    glow: "hover:shadow-[0_8px_30px_rgb(100,116,139,0.12)]",
    barColor: "bg-slate-700",
  },
}

export function DashboardMetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
  color = "blue",
  trend,
  progress,
  onClick,
  badge,
}: DashboardMetricCardProps) {
  const styles = COLOR_STYLES[color]

  return (
    <div
      onClick={onClick}
      className={`relative rounded-2xl p-5 border ${styles.border} ${styles.bg} shadow-sm ${styles.glow} transition-all duration-200 flex flex-col justify-between ${
        onClick ? "cursor-pointer transform hover:-translate-y-1" : ""
      }`}
    >
      {/* Top row: label + icon */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold tracking-wider uppercase text-slate-500">
            {label}
          </span>
          {badge && (
            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700">
              {badge}
            </span>
          )}
        </div>
        <div className={`p-2.5 rounded-xl shrink-0 ${styles.iconBg}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>

      {/* Main value */}
      <div className="mt-3">
        <div className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#0b1930]">
          {value}
        </div>

        {sublabel && (
          <div className="text-xs font-medium text-slate-500 mt-1 flex items-center gap-1.5">
            {sublabel}
          </div>
        )}

        {/* Progress bar if present */}
        {progress && (
          <div className="mt-3">
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${styles.barColor}`}
                style={{ width: `${Math.min(100, Math.max(0, progress.value))}%` }}
              />
            </div>
          </div>
        )}

        {/* Trend pill if present */}
        {trend && (
          <div className="mt-2.5 flex items-center gap-1.5 text-xs font-semibold">
            {trend.direction === "up" && (
              <span
                className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                  trend.positive !== false
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200/80"
                    : "bg-rose-50 text-rose-700 border border-rose-200/80"
                }`}
              >
                <TrendingUpIcon className="w-3 h-3" />
                {trend.label}
              </span>
            )}
            {trend.direction === "down" && (
              <span
                className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                  trend.positive
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200/80"
                    : "bg-rose-50 text-rose-700 border border-rose-200/80"
                }`}
              >
                <TrendingDownIcon className="w-3 h-3" />
                {trend.label}
              </span>
            )}
            {trend.direction === "neutral" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600">
                {trend.label}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
