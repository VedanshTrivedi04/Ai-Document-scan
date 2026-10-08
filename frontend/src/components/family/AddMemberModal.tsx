import * as React from "react"
import { Loader2Icon, UserPlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { MemberCreatePayload } from "@/types/family"

interface AddMemberModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (payload: MemberCreatePayload) => Promise<void>
  isSubmitting?: boolean
  currentLang?: string
}

const MODAL_I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Add family member",
    description: "Add a member of your household. You can submit a document bundle for them afterwards.",
    full_name: "Full name",
    full_name_placeholder: "e.g. Sarla Agrawal",
    relation: "Relation to head",
    select_relation: "Select relation…",
    date_of_birth: "Date of birth (optional)",
    cancel: "Cancel",
    add: "Add member",
    name_required: "Full name is required",
    relation_required: "Please select a relation",
  },
  hi: {
    title: "परिवार का सदस्य जोड़ें",
    description: "अपने घर के किसी सदस्य को जोड़ें। इसके बाद आप उनके दस्तावेज़ जमा कर सकते हैं।",
    full_name: "पूरा नाम",
    full_name_placeholder: "उदा. सरला अग्रवाल",
    relation: "मुखिया से संबंध",
    select_relation: "संबंध चुनें…",
    date_of_birth: "जन्म तिथि (वैकल्पिक)",
    cancel: "रद्द करें",
    add: "सदस्य जोड़ें",
    name_required: "पूरा नाम आवश्यक है",
    relation_required: "कृपया संबंध चुनें",
  },
}

const RELATION_OPTIONS = [
  { value: "spouse", label: "Spouse (पति / पत्नी)" },
  { value: "son", label: "Son (पुत्र)" },
  { value: "daughter", label: "Daughter (पुत्री)" },
  { value: "father", label: "Father (पिता)" },
  { value: "mother", label: "Mother (माता)" },
  { value: "other", label: "Other (अन्य)" },
]

export function AddMemberModal(props: AddMemberModalProps) {
  if (!props.isOpen) return null
  return <AddMemberDialogInner key="add-member-dialog" {...props} />
}

function AddMemberDialogInner({
  onClose,
  onAdd,
  isSubmitting = false,
  currentLang = "en",
}: AddMemberModalProps) {
  const [fullName, setFullName] = React.useState("")
  const [relation, setRelation] = React.useState<MemberCreatePayload["relation"]>("spouse")
  const [dateOfBirth, setDateOfBirth] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = MODAL_I18N[langKey] ?? MODAL_I18N.en

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fullName.trim()) {
      setError(t.name_required)
      return
    }
    if (!relation) {
      setError(t.relation_required)
      return
    }

    try {
      setError(null)
      await onAdd({
        full_name: fullName.trim(),
        relation,
        date_of_birth: dateOfBirth || null,
      })
      onClose()
    } catch (err: any) {
      setError(err?.message || "Failed to add member")
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-2xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl flex flex-col gap-4 font-sans">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-border/80">
          <div className="flex items-center gap-2">
            <UserPlusIcon className="size-4.5 text-primary" />
            <h3 className="text-base font-bold text-foreground">{t.title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-muted-foreground hover:text-foreground rounded-md"
          >
            <XIcon className="size-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground -mt-1">{t.description}</p>

        {error && (
          <div className="p-2.5 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5 text-xs">
          {/* Full Name */}
          <div className="flex flex-col gap-1">
            <label className="font-semibold text-foreground">
              {t.full_name} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t.full_name_placeholder}
              className="px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"
            />
          </div>

          {/* Relation */}
          <div className="flex flex-col gap-1">
            <label className="font-semibold text-foreground">
              {t.relation} <span className="text-red-500">*</span>
            </label>
            <select
              required
              value={relation}
              onChange={(e) =>
                setRelation(e.target.value as MemberCreatePayload["relation"])
              }
              className="px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs cursor-pointer"
            >
              {RELATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Date of Birth */}
          <div className="flex flex-col gap-1">
            <label className="font-semibold text-foreground">{t.date_of_birth}</label>
            <input
              type="date"
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
              className="px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/80 mt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
              className="h-8 text-xs font-semibold"
            >
              {t.cancel}
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="h-8 text-xs font-semibold gap-1.5"
            >
              {isSubmitting && <Loader2Icon className="size-3.5 animate-spin" />}
              <span>{t.add}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
