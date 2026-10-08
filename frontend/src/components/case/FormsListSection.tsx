import { useQuery } from "@tanstack/react-query"
import { ArrowRightIcon, FileCheck2Icon, FileTextIcon, Loader2Icon } from "lucide-react"
import { Link } from "react-router-dom"

import { listForms } from "@/api/profiles"
import { Button } from "@/components/ui/button"

interface FormsListSectionProps {
  caseId: string
  caseType?: string | null
  currentLang?: string
  token: string | null
}

const FORMS_I18N: Record<string, Record<string, string>> = {
  en: {
    section_title: "Fill a form",
    section_subtitle: "Application forms pre-filled directly from this person's verified documents.",
    loading: "Loading available forms…",
    no_forms: "No application forms currently available for this case type.",
    open_form: "Open form",
    filled_badge: "fields filled from documents",
    of: "of",
    from_docs: "fields filled from your documents",
  },
  hi: {
    section_title: "प्रपत्र भरें",
    section_subtitle: "इस व्यक्ति के सत्यापित दस्तावेज़ों से स्वतः भरे जाने वाले आधिकारिक आवेदन प्रपत्र।",
    loading: "उपलब्ध प्रपत्र लोड हो रहे हैं…",
    no_forms: "इस प्रकार के मामले के लिए वर्तमान में कोई प्रपत्र उपलब्ध नहीं है।",
    open_form: "प्रपत्र खोलें",
    filled_badge: "फ़ील्ड दस्तावेज़ों से भरे हुए",
    of: "/",
    from_docs: "फ़ील्ड आपके दस्तावेज़ों से भरे गए",
  },
}

export function FormsListSection({
  caseId,
  caseType,
  currentLang = "en",
  token,
}: FormsListSectionProps) {
  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = FORMS_I18N[langKey] ?? FORMS_I18N.en

  const { data: forms = [], isLoading } = useQuery({
    queryKey: ["formsList", caseType, currentLang, token],
    queryFn: () => (token ? listForms(caseType, currentLang, token) : Promise.resolve([])),
    enabled: Boolean(token && caseId),
  })

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans">
      {/* Header */}
      <div className="flex flex-col gap-0.5 pb-3 border-b border-border/80">
        <div className="flex items-center gap-2">
          <FileCheck2Icon className="size-4.5 text-primary" />
          <h3 className="text-sm font-bold text-foreground">{t.section_title}</h3>
        </div>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          {t.section_subtitle}
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
          <Loader2Icon className="size-4 animate-spin text-primary" />
          <span>{t.loading}</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && forms.length === 0 && (
        <div className="text-xs text-muted-foreground py-3 italic">
          {t.no_forms}
        </div>
      )}

      {/* Forms List */}
      {!isLoading && forms.length > 0 && (
        <div className="flex flex-col gap-3">
          {forms.map((form) => {
            const isFull = form.prefilled_field_count === form.field_count

            return (
              <div
                key={form.id}
                className="p-3.5 rounded-xl border border-border/80 bg-background hover:border-primary/40 hover:shadow-xs transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <FileTextIcon className="size-4 text-primary shrink-0" />
                    <span className="font-bold text-foreground text-sm truncate">
                      {form.title}
                    </span>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                        isFull
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-blue-50 text-blue-800 border-blue-200"
                      }`}
                    >
                      {form.prefilled_field_count} {t.of} {form.field_count} {t.from_docs}
                    </span>
                  </div>
                  {form.description && (
                    <p className="text-[11px] text-muted-foreground line-clamp-2">
                      {form.description}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                  <Button
                    asChild
                    size="sm"
                    className="h-8 px-3 text-xs font-semibold gap-1.5"
                  >
                    <Link to={`/cases/${caseId}/forms/${form.id}`}>
                      <span>{t.open_form}</span>
                      <ArrowRightIcon className="size-3.5" />
                    </Link>
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
