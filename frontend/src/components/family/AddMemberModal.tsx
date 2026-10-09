import * as React from "react"
import { Loader2Icon, UserPlusIcon, XIcon } from "lucide-react"

import { MemberCredentialsDialog } from "@/components/family/MemberCredentialsDialog"
import { Button } from "@/components/ui/button"
import { FieldError, invalidFieldClass } from "@/components/ui/field-error"
import type { FamilyView, MemberCreatePayload } from "@/types/family"

interface AddMemberModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (payload: MemberCreatePayload) => Promise<FamilyView | void>
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
    create_login: "Create a sign-in for this person",
    create_login_help: "They can sign in with their own account and see only their own documents. You still manage everything.",
    login_email: "Their email",
    login_password: "Password (optional)",
    login_password_help: "Leave empty to generate a temporary one. They must change it at first sign-in.",
    email_invalid: "Enter a valid email address.",
    password_short: "Use at least 8 characters, or leave it empty.",
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
    create_login: "इस व्यक्ति के लिए साइन-इन बनाएँ",
    create_login_help: "वे अपने अकाउंट से साइन-इन करके केवल अपने दस्तावेज़ देख सकेंगे। सब कुछ आप ही संभालेंगे।",
    login_email: "उनका ईमेल",
    login_password: "पासवर्ड (वैकल्पिक)",
    login_password_help: "खाली छोड़ें तो अस्थायी पासवर्ड बन जाएगा। पहली बार साइन-इन पर उन्हें इसे बदलना होगा।",
    email_invalid: "सही ईमेल पता लिखें।",
    password_short: "कम से कम 8 अक्षर रखें, या खाली छोड़ें।",
  },
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

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
  const [withLogin, setWithLogin] = React.useState(false)
  const [loginEmail, setLoginEmail] = React.useState("")
  const [loginPassword, setLoginPassword] = React.useState("")
  const [submitted, setSubmitted] = React.useState(false)
  const [created, setCreated] = React.useState<FamilyView["credentials"] | null>(null)

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = MODAL_I18N[langKey] ?? MODAL_I18N.en

  const emailError = withLogin && !EMAIL_PATTERN.test(loginEmail.trim()) ? t.email_invalid : null
  const passwordError = withLogin && loginPassword && loginPassword.length < 8 ? t.password_short : null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (emailError || passwordError) return
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
      const view = await onAdd({
        full_name: fullName.trim(),
        relation,
        date_of_birth: dateOfBirth || null,
        ...(withLogin
          ? { login: { email: loginEmail.trim(), password: loginPassword || undefined } }
          : {}),
      })
      if (view && "credentials" in view && view.credentials) {
        setCreated(view.credentials)
        return
      }
      onClose()
    } catch (err: any) {
      setError(err?.message || "Failed to add member")
    }
  }

  if (created) {
    return (
      <MemberCredentialsDialog
        credentials={created}
        memberName={fullName.trim()}
        onClose={onClose}
        currentLang={currentLang}
      />
    )
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

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3.5 text-xs">
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

          {/* Optional sign-in for this member */}
          <div className="rounded-xl border border-border/80 bg-muted/20 p-3 flex flex-col gap-2.5">
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={withLogin}
                onChange={(e) => setWithLogin(e.target.checked)}
                className="mt-0.5 size-3.5 accent-primary"
              />
              <span>
                <span className="font-semibold text-foreground block">{t.create_login}</span>
                <span className="text-[11px] text-muted-foreground">{t.create_login_help}</span>
              </span>
            </label>
            {withLogin && (
              <div className="flex flex-col gap-2.5 pl-5">
                <div className="flex flex-col gap-1">
                  <label htmlFor="add-member-login-email" className="font-semibold text-foreground">
                    {t.login_email}
                  </label>
                  <input
                    id="add-member-login-email"
                    type="email"
                    autoComplete="off"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    className={`px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs ${submitted && emailError ? invalidFieldClass : ""}`}
                  />
                  <FieldError id="add-member-login-email-error" message={submitted ? emailError : null} />
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="add-member-login-password" className="font-semibold text-foreground">
                    {t.login_password}
                  </label>
                  <input
                    id="add-member-login-password"
                    type="text"
                    autoComplete="off"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className={`px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs ${submitted && passwordError ? invalidFieldClass : ""}`}
                  />
                  <p className="text-[11px] text-muted-foreground">{t.login_password_help}</p>
                  <FieldError id="add-member-login-password-error" message={submitted ? passwordError : null} />
                </div>
              </div>
            )}
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
