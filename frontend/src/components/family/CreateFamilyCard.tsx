import * as React from "react"
import { HomeIcon, Loader2Icon, SparklesIcon, UsersIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { FamilyCreatePayload } from "@/types/family"

interface CreateFamilyCardProps {
  onCreate: (payload: FamilyCreatePayload) => Promise<void>
  isCreating?: boolean
  currentLang?: string
}

const CREATE_I18N: Record<string, Record<string, string>> = {
  en: {
    badge: "Household Verification",
    title: "Set up your family",
    description: "Manage verification documents for your entire household in one place. Add your family members, upload their identity bundles, and view automated family-level consistency checks.",
    family_name: "Family name (optional)",
    family_name_placeholder: "e.g. Agrawal family",
    family_name_hint: "Defaults to your name + 'family' if left blank.",
    head_dob: "Your date of birth (optional)",
    submit_button: "Create family",
  },
  hi: {
    badge: "पारिवारिक सत्यापन",
    title: "अपना परिवार बनाएं",
    description: "अपने पूरे परिवार के सत्यापन दस्तावेज़ों को एक ही स्थान पर प्रबंधित करें। परिवार के सदस्यों को जोड़ें, उनके पहचान दस्तावेज़ अपलोड करें, और स्वतः परिवार-स्तरीय सामंजस्य जाँचें देखें।",
    family_name: "परिवार का नाम (वैकल्पिक)",
    family_name_placeholder: "उदा. अग्रवाल परिवार",
    family_name_hint: "खाली छोड़ने पर स्वतः आपके नाम के साथ 'परिवार' जुड़ जाएगा।",
    head_dob: "आपकी जन्म तिथि (वैकल्पिक)",
    submit_button: "परिवार बनाएं",
  },
}

export function CreateFamilyCard({
  onCreate,
  isCreating = false,
  currentLang = "en",
}: CreateFamilyCardProps) {
  const [familyName, setFamilyName] = React.useState("")
  const [headDob, setHeadDob] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = CREATE_I18N[langKey] ?? CREATE_I18N.en

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setError(null)
      await onCreate({
        name: familyName.trim() || undefined,
        head_date_of_birth: headDob || undefined,
      })
    } catch (err: any) {
      setError(err?.message || "Failed to create family")
    }
  }

  return (
    <div className="max-w-2xl w-full mx-auto bg-card rounded-2xl border border-border p-6 sm:p-10 shadow-sm flex flex-col gap-6 font-sans">
      <div className="flex flex-col gap-2 text-center items-center">
        <div className="size-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-1">
          <HomeIcon className="size-6" />
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
          <SparklesIcon className="size-3" />
          {t.badge}
        </span>
        <h2 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">
          {t.title}
        </h2>
        <p className="text-xs sm:text-sm text-muted-foreground max-w-lg leading-relaxed">
          {t.description}
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-xs text-destructive">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-xs max-w-md mx-auto w-full">
        {/* Family Name */}
        <div className="flex flex-col gap-1">
          <label className="font-semibold text-foreground">{t.family_name}</label>
          <input
            type="text"
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
            placeholder={t.family_name_placeholder}
            className="px-3.5 py-2.5 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"
          />
          <span className="text-[11px] text-muted-foreground">{t.family_name_hint}</span>
        </div>

        {/* Head Date of Birth */}
        <div className="flex flex-col gap-1">
          <label className="font-semibold text-foreground">{t.head_dob}</label>
          <input
            type="date"
            value={headDob}
            onChange={(e) => setHeadDob(e.target.value)}
            className="px-3.5 py-2.5 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs"
          />
        </div>

        <Button
          type="submit"
          disabled={isCreating}
          className="mt-2 h-10 text-xs font-bold gap-2 rounded-xl"
        >
          {isCreating ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <UsersIcon className="size-4" />
          )}
          <span>{t.submit_button}</span>
        </Button>
      </form>
    </div>
  )
}
