import * as React from "react"
import { Edit2Icon, Loader2Icon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { FamilyMember, MemberUpdatePayload } from "@/types/family"

interface EditMemberModalProps {
  member: FamilyMember | null
  isOpen: boolean
  onClose: () => void
  onUpdate: (memberId: string, payload: MemberUpdatePayload) => Promise<void>
  isSubmitting?: boolean
  currentLang?: string
}

const EDIT_I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Correct member details",
    description: "Update the registered name, relation, or date of birth for this member.",
    full_name: "Full name",
    relation: "Relation to head",
    head_relation_locked: "The head of the family always keeps the relation 'self'.",
    date_of_birth: "Date of birth",
    cancel: "Cancel",
    save: "Save changes",
    name_required: "Full name is required",
  },
  hi: {
    title: "सदस्य विवरण संशोधित करें",
    description: "इस सदस्य का नाम, संबंध या जन्म तिथि अद्यतन करें।",
    full_name: "पूरा नाम",
    relation: "मुखिया से संबंध",
    head_relation_locked: "परिवार के मुखिया का संबंध हमेशा 'स्वयं' रहता है।",
    date_of_birth: "जन्म तिथि",
    cancel: "रद्द करें",
    save: "परिवर्तन सहेजें",
    name_required: "पूरा नाम आवश्यक है",
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

export function EditMemberModal(props: EditMemberModalProps) {
  if (!props.isOpen || !props.member) return null
  return <EditMemberDialogInner key={props.member.id} {...props} member={props.member} />
}

function EditMemberDialogInner({
  member,
  onClose,
  onUpdate,
  isSubmitting = false,
  currentLang = "en",
}: EditMemberModalProps & { member: FamilyMember }) {
  const [fullName, setFullName] = React.useState(member.full_name)
  const [relation, setRelation] = React.useState<MemberUpdatePayload["relation"]>(
    member.relation === "self" ? undefined : (member.relation as any)
  )
  const [dateOfBirth, setDateOfBirth] = React.useState(member.date_of_birth || "")
  const [error, setError] = React.useState<string | null>(null)

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = EDIT_I18N[langKey] ?? EDIT_I18N.en

  const isHead = member.is_head

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fullName.trim()) {
      setError(t.name_required)
      return
    }

    try {
      setError(null)
      const payload: MemberUpdatePayload = {
        full_name: fullName.trim(),
        date_of_birth: dateOfBirth || null,
      }
      if (!isHead && relation) {
        payload.relation = relation
      }
      await onUpdate(member.id, payload)
      onClose()
    } catch (err: any) {
      setError(err?.message || "Failed to update member")
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-2xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl flex flex-col gap-4 font-sans">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-border/80">
          <div className="flex items-center gap-2">
            <Edit2Icon className="size-4.5 text-primary" />
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
              className="px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"
            />
          </div>

          {/* Relation */}
          <div className="flex flex-col gap-1">
            <label className="font-semibold text-foreground">{t.relation}</label>
            {isHead ? (
              <p className="text-[11px] text-muted-foreground italic px-1">
                {t.head_relation_locked}
              </p>
            ) : (
              <select
                value={relation}
                onChange={(e) =>
                  setRelation(e.target.value as MemberUpdatePayload["relation"])
                }
                className="px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs cursor-pointer"
              >
                {RELATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            )}
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
              <span>{t.save}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
