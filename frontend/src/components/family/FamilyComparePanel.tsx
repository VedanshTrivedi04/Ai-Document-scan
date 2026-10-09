import * as React from "react"
import { AlertTriangleIcon, GitCompareArrowsIcon, Loader2Icon } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import type { ComparisonListItem, FamilyMember } from "@/types/family"

interface FamilyComparePanelProps {
  members: FamilyMember[]
  comparisons: ComparisonListItem[]
  onCompare: (memberIds: string[]) => Promise<void>
  isComparing?: boolean
  error?: string | null
  currentLang?: string
}

const I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Compare family members",
    subtitle:
      "Check the verified details of members against each other and against yours: address, parents' names, dates of birth. Each conflict can be accepted or dismissed, and is kept on record.",
    pick: "Choose who to compare with you",
    run: "Run comparison",
    start: "New comparison",
    cancel: "Cancel",
    none_to_pick: "Add a family member first.",
    no_docs: "no documents yet",
    previous: "Your comparisons",
    conflicts: "conflicts",
    open: "open",
    clean: "No conflicts",
    pick_one: "Pick at least one member.",
  },
  hi: {
    title: "परिवार के सदस्यों की तुलना",
    subtitle:
      "सदस्यों की सत्यापित जानकारी को एक-दूसरे से और अपनी जानकारी से मिलाएँ: पता, माता-पिता के नाम, जन्म तिथियाँ। हर अंतर को स्वीकार या खारिज किया जा सकता है और वह रिकॉर्ड में रहता है।",
    pick: "आपके साथ किन सदस्यों की तुलना करनी है, चुनें",
    run: "तुलना चलाएँ",
    start: "नई तुलना",
    cancel: "रद्द करें",
    none_to_pick: "पहले कोई सदस्य जोड़ें।",
    no_docs: "अभी दस्तावेज़ नहीं",
    previous: "आपकी तुलनाएँ",
    conflicts: "अंतर",
    open: "लंबित",
    clean: "कोई अंतर नहीं",
    pick_one: "कम से कम एक सदस्य चुनें।",
  },
}

/** Head only: start a comparison of members, and the earlier ones. */
export function FamilyComparePanel({
  members,
  comparisons,
  onCompare,
  isComparing = false,
  error,
  currentLang = "en",
}: FamilyComparePanelProps) {
  const t = I18N[currentLang === "hi" ? "hi" : "en"]
  const others = members.filter((m) => !m.is_head)
  const [picking, setPicking] = React.useState(false)
  const [selected, setSelected] = React.useState<string[]>([])
  const [submitted, setSubmitted] = React.useState(false)

  const toggle = (id: string) =>
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]))

  const run = async () => {
    setSubmitted(true)
    if (selected.length === 0) return
    await onCompare(selected)
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans" aria-label={t.title}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <GitCompareArrowsIcon className="size-4.5 text-primary" />
            <h3 className="text-sm font-bold text-foreground">{t.title}</h3>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">{t.subtitle}</p>
        </div>
        {!picking && (
          <Button
            type="button"
            size="sm"
            disabled={others.length === 0}
            onClick={() => setPicking(true)}
            className="h-8 text-xs font-bold gap-1.5 rounded-xl"
          >
            <GitCompareArrowsIcon className="size-3.5" />
            {t.start}
          </Button>
        )}
      </div>

      {others.length === 0 && <p className="text-xs text-muted-foreground italic">{t.none_to_pick}</p>}

      {picking && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 flex flex-col gap-2.5">
          <p className="text-xs font-semibold text-foreground">{t.pick}</p>
          <ul className="flex flex-col gap-1.5">
            {others.map((m) => (
              <li key={m.id}>
                <label className="flex items-center gap-2 rounded-lg border border-border/70 bg-background px-3 py-2 text-xs cursor-pointer hover:border-primary/40">
                  <input
                    type="checkbox"
                    checked={selected.includes(m.id)}
                    onChange={() => toggle(m.id)}
                    className="size-3.5 accent-primary"
                  />
                  <span className="font-semibold">{m.full_name}</span>
                  <span className="text-muted-foreground">({m.relation_label})</span>
                  {m.cases.length === 0 && <span className="ml-auto text-[11px] text-amber-700">{t.no_docs}</span>}
                </label>
              </li>
            ))}
          </ul>
          {submitted && selected.length === 0 && (
            <p role="alert" className="text-[11px] font-medium text-rose-600">
              {t.pick_one}
            </p>
          )}
          {error && (
            <p role="alert" className="text-[11px] font-medium text-rose-600">
              {error}
            </p>
          )}
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              disabled={isComparing}
              onClick={() => {
                setPicking(false)
                setSelected([])
                setSubmitted(false)
              }}
            >
              {t.cancel}
            </Button>
            <Button type="button" size="sm" className="h-8 text-xs font-semibold gap-1.5" disabled={isComparing} onClick={run}>
              {isComparing && <Loader2Icon className="size-3.5 animate-spin" />}
              {t.run}
            </Button>
          </div>
        </div>
      )}

      {comparisons.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{t.previous}</h4>
          <ul className="flex flex-col gap-1.5">
            {comparisons.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/family/compare/${c.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background px-3 py-2 text-xs hover:border-primary/40"
                >
                  <span className="min-w-0">
                    <span className="font-mono font-semibold text-primary">{c.case_number}</span>
                    <span className="text-muted-foreground"> · {c.members.join(", ")}</span>
                  </span>
                  <span className="shrink-0">
                    {c.conflicts === 0 ? (
                      <span className="text-emerald-700 font-medium">{t.clean}</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-destructive font-semibold">
                        <AlertTriangleIcon className="size-3" />
                        {c.conflicts} {t.conflicts}
                        {c.open_conflicts > 0 ? ` · ${c.open_conflicts} ${t.open}` : ""}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
