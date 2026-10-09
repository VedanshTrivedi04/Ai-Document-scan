import * as React from "react"
import { CheckIcon, CopyIcon, KeyRoundIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { MemberCredentials } from "@/types/family"

interface MemberCredentialsDialogProps {
  credentials: MemberCredentials
  memberName: string
  onClose: () => void
  currentLang?: string
}

const I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Sign-in ready",
    intro: "Share these details privately. The password is shown only now.",
    email: "Email",
    password: "Temporary password",
    chosen: "The password you chose",
    must_change: "They will be asked to choose their own password the first time they sign in.",
    copy: "Copy",
    copied: "Copied",
    copy_both: "Copy both",
    done: "I have noted it",
  },
  hi: {
    title: "साइन-इन तैयार है",
    intro: "ये जानकारी केवल उन्हें निजी तौर पर दें। पासवर्ड सिर्फ अभी दिखता है।",
    email: "ईमेल",
    password: "अस्थायी पासवर्ड",
    chosen: "आपका चुना हुआ पासवर्ड",
    must_change: "पहली बार साइन-इन करने पर उनसे अपना पासवर्ड चुनने को कहा जाएगा।",
    copy: "कॉपी करें",
    copied: "कॉपी हो गया",
    copy_both: "दोनों कॉपी करें",
    done: "मैंने नोट कर लिया",
  },
}

/** The one-time card shown after a sign-in is created or its password reset. */
export function MemberCredentialsDialog({
  credentials,
  memberName,
  onClose,
  currentLang = "en",
}: MemberCredentialsDialogProps) {
  const t = I18N[currentLang === "hi" ? "hi" : "en"]
  const [copied, setCopied] = React.useState<string | null>(null)

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(key)
      window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800)
    } catch {
      // Clipboard can be blocked; the values are on screen to copy by hand.
    }
  }

  const password = credentials.temporary_password
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-2xs p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t.title}
        className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl flex flex-col gap-4 font-sans"
      >
        <div className="flex items-center justify-between pb-3 border-b border-border/80">
          <div className="flex items-center gap-2">
            <KeyRoundIcon className="size-4.5 text-primary" />
            <h3 className="text-base font-bold text-foreground">
              {t.title} · {memberName}
            </h3>
          </div>
          <button type="button" onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground rounded-md">
            <XIcon className="size-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground -mt-1">{t.intro}</p>

        <dl className="flex flex-col gap-3 text-xs">
          <div className="rounded-xl border border-border bg-background p-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{t.email}</dt>
              <dd className="font-mono text-sm font-semibold break-all">{credentials.email}</dd>
            </div>
            <Button type="button" size="sm" variant="outline" className="h-7 text-[11px] gap-1" onClick={() => copy("email", credentials.email)}>
              {copied === "email" ? <CheckIcon className="size-3" /> : <CopyIcon className="size-3" />}
              {copied === "email" ? t.copied : t.copy}
            </Button>
          </div>

          <div className="rounded-xl border border-amber-300 bg-amber-50/70 p-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-amber-800">
                {password ? t.password : t.chosen}
              </dt>
              <dd className="font-mono text-base font-bold tracking-wide break-all select-all">
                {password ?? "••••••••"}
              </dd>
            </div>
            {password && (
              <Button type="button" size="sm" variant="outline" className="h-7 text-[11px] gap-1" onClick={() => copy("password", password)}>
                {copied === "password" ? <CheckIcon className="size-3" /> : <CopyIcon className="size-3" />}
                {copied === "password" ? t.copied : t.copy}
              </Button>
            )}
          </div>
        </dl>

        <p className="text-[11px] text-muted-foreground">{t.must_change}</p>

        <div className="flex items-center justify-between gap-2 pt-3 border-t border-border/80">
          {password ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-[11px] gap-1"
              onClick={() => copy("both", `Email: ${credentials.email}\nPassword: ${password}`)}
            >
              {copied === "both" ? <CheckIcon className="size-3" /> : <CopyIcon className="size-3" />}
              {copied === "both" ? t.copied : t.copy_both}
            </Button>
          ) : (
            <span />
          )}
          <Button type="button" size="sm" onClick={onClose} className="h-8 text-xs font-semibold">
            {t.done}
          </Button>
        </div>
      </div>
    </div>
  )
}
