import * as React from "react"
import { KeyRoundIcon, Loader2Icon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { FieldError, invalidFieldClass } from "@/components/ui/field-error"
import type { FamilyMember, MemberLoginPayload } from "@/types/family"

interface MemberLoginDialogProps {
  member: FamilyMember | null
  onClose: () => void
  onCreate: (memberId: string, payload: MemberLoginPayload) => Promise<void>
  isSubmitting?: boolean
  currentLang?: string
}

const I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Create a sign-in",
    intro: "Lets this person sign in with their own account and see only their own documents. You stay in charge of them.",
    email: "Email",
    password: "Password (optional)",
    password_help: "Leave empty to generate a temporary one. They must change it at first sign-in.",
    cancel: "Cancel",
    create: "Create sign-in",
    email_invalid: "Enter a valid email address.",
    password_short: "Use at least 8 characters, or leave it empty.",
    failed: "Could not create the sign-in.",
  },
  hi: {
    title: "साइन-इन बनाएँ",
    intro: "इससे यह व्यक्ति अपने अकाउंट से साइन-इन करके केवल अपने दस्तावेज़ देख सकेगा। नियंत्रण आपके पास रहेगा।",
    email: "ईमेल",
    password: "पासवर्ड (वैकल्पिक)",
    password_help: "खाली छोड़ें तो अस्थायी पासवर्ड बन जाएगा। पहली बार साइन-इन पर उन्हें इसे बदलना होगा।",
    cancel: "रद्द करें",
    create: "साइन-इन बनाएँ",
    email_invalid: "सही ईमेल पता लिखें।",
    password_short: "कम से कम 8 अक्षर रखें, या खाली छोड़ें।",
    failed: "साइन-इन नहीं बन सका।",
  },
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function MemberLoginDialog(props: MemberLoginDialogProps) {
  if (!props.member) return null
  return <Inner key={props.member.id} {...props} member={props.member} />
}

function Inner({
  member,
  onClose,
  onCreate,
  isSubmitting = false,
  currentLang = "en",
}: MemberLoginDialogProps & { member: FamilyMember }) {
  const t = I18N[currentLang === "hi" ? "hi" : "en"]
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [submitted, setSubmitted] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const emailError = EMAIL_PATTERN.test(email.trim()) ? null : t.email_invalid
  const passwordError = password && password.length < 8 ? t.password_short : null

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitted(true)
    setError(null)
    if (emailError || passwordError) return
    try {
      await onCreate(member.id, { email: email.trim(), password: password || undefined })
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t.failed)
    }
  }

  const inputClass =
    "px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-2xs p-4">
      <form
        onSubmit={submit}
        noValidate
        className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl flex flex-col gap-4 font-sans"
      >
        <div className="flex items-center justify-between pb-3 border-b border-border/80">
          <div className="flex items-center gap-2">
            <KeyRoundIcon className="size-4.5 text-primary" />
            <h3 className="text-base font-bold text-foreground">
              {t.title} · {member.full_name}
            </h3>
          </div>
          <button type="button" onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground rounded-md">
            <XIcon className="size-4" />
          </button>
        </div>
        <p className="text-xs text-muted-foreground -mt-1">{t.intro}</p>

        {error && (
          <div role="alert" className="p-2.5 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3.5 text-xs">
          <div className="flex flex-col gap-1">
            <label htmlFor="member-login-email" className="font-semibold text-foreground">
              {t.email}
            </label>
            <input
              id="member-login-email"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`${inputClass} ${submitted && emailError ? invalidFieldClass : ""}`}
            />
            <FieldError id="member-login-email-error" message={submitted ? emailError : null} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="member-login-password" className="font-semibold text-foreground">
              {t.password}
            </label>
            <input
              id="member-login-password"
              type="text"
              autoComplete="off"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${inputClass} ${submitted && passwordError ? invalidFieldClass : ""}`}
            />
            <p className="text-[11px] text-muted-foreground">{t.password_help}</p>
            <FieldError id="member-login-password-error" message={submitted ? passwordError : null} />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/80">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting} className="h-8 text-xs font-semibold">
            {t.cancel}
          </Button>
          <Button type="submit" size="sm" disabled={isSubmitting} className="h-8 text-xs font-semibold gap-1.5">
            {isSubmitting && <Loader2Icon className="size-3.5 animate-spin" />}
            <span>{t.create}</span>
          </Button>
        </div>
      </form>
    </div>
  )
}
