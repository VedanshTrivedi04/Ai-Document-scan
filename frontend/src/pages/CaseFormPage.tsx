import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import {
  AlertTriangleIcon,
  ChevronLeftIcon,
  ExternalLinkIcon,
  GlobeIcon,
  HelpCircleIcon,
  Loader2Icon,
  LockIcon,
  PrinterIcon,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"

import { getCatalog, getLanguages } from "@/api/i18n"
import { getPrefilledForm } from "@/api/profiles"
import { Button } from "@/components/ui/button"
import { Nav } from "@/design-system/Nav"
import { useAuth } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { DOCUMENT_TYPE_LABELS, type PrefilledFormField } from "@/types/case"

const FORM_PAGE_I18N: Record<string, Record<string, string>> = {
  en: {
    back_to_case: "Back to case",
    print: "Print",
    print_draft: "Print draft",
    draft_banner: "Some details are in conflict. Settle them to complete this form.",
    review_conflicts: "Review conflicts",
    filled: "filled",
    needs_attention: "needs attention",
    for_you_to_fill: "for you to fill",
    from: "From",
    why_cant_edit: "This comes from your verified documents.",
    see_conflict: "See the conflict",
    select_placeholder: "Select an option…",
    loading_form: "Loading pre-filled form…",
    form_not_found: "Form not found or inaccessible.",
    case_label: "Case",
  },
  hi: {
    back_to_case: "मामले पर वापस जाएं",
    print: "प्रिंट करें",
    print_draft: "ड्राफ्ट प्रिंट करें",
    draft_banner: "कुछ विवरणों में विरोधाभास है। इस प्रपत्र को पूरा करने के लिए उन्हें सुलझाएं।",
    review_conflicts: "विवादों की समीक्षा करें",
    filled: "भरे हुए",
    needs_attention: "ध्यान देने योग्य",
    for_you_to_fill: "आपको भरने हैं",
    from: "स्रोत:",
    why_cant_edit: "यह आपके सत्यापित दस्तावेज़ों से आया है।",
    see_conflict: "विवाद देखें",
    select_placeholder: "एक विकल्प चुनें…",
    loading_form: "स्वतः भरा प्रपत्र लोड हो रहा है…",
    form_not_found: "प्रपत्र नहीं मिला या उस तक पहुंच नहीं है।",
    case_label: "मामला",
  },
}

export function CaseFormPage() {
  const params = useParams<{ caseId?: string; id?: string; formId?: string }>()
  const caseId = params.caseId || params.id
  const formId = params.formId

  const { token } = useAuth()

  const [currentLang, setCurrentLang] = React.useState<string>(() => {
    try {
      return localStorage.getItem("docsure_lang") || "en"
    } catch {
      return "en"
    }
  })

  React.useEffect(() => {
    try {
      localStorage.setItem("docsure_lang", currentLang)
    } catch {
      // ignore
    }
  }, [currentLang])

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = FORM_PAGE_I18N[langKey] ?? FORM_PAGE_I18N.en

  // Available languages
  const { data: languages = [] } = useQuery({
    queryKey: ["i18nLanguages"],
    queryFn: () => getLanguages(),
    staleTime: 5 * 60 * 1000,
  })
  const availableLanguages = React.useMemo(() => languages.filter((l) => l.available), [languages])

  // Catalog for translated document names
  const { data: catalog = null } = useQuery({
    queryKey: ["i18nCatalog", currentLang, token],
    queryFn: () => (token ? getCatalog(currentLang, token) : Promise.resolve(null)),
    enabled: Boolean(token),
    staleTime: 5 * 60 * 1000,
  })

  // Prefilled Form Data
  const {
    data: formData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["prefilledForm", caseId, formId, currentLang, token],
    queryFn: () => {
      if (!caseId || !formId || !token) throw new Error("Missing parameters")
      return getPrefilledForm(caseId, formId, currentLang, token)
    },
    enabled: Boolean(caseId && formId && token),
  })

  // Local state for user-editable fields (status === 'to_fill'), persisted in localStorage
  const storageKey = React.useMemo(() => {
    return caseId && formId ? `form_values_${caseId}_${formId}` : null
  }, [caseId, formId])

  const [userInputs, setUserInputs] = React.useState<Record<string, string>>(() => {
    if (!storageKey) return {}
    try {
      const saved = localStorage.getItem(storageKey)
      return saved ? JSON.parse(saved) : {}
    } catch {
      return {}
    }
  })

  const handleInputChange = (key: string, value: string) => {
    setUserInputs((prev) => {
      const next = { ...prev, [key]: value }
      if (storageKey) {
        try {
          localStorage.setItem(storageKey, JSON.stringify(next))
        } catch {
          // ignore
        }
      }
      return next
    })
  }

  const getDocTypeLabel = (docType: string | null | undefined): string => {
    if (!docType) return "Document"
    return catalog?.documents?.[docType] ?? DOCUMENT_TYPE_LABELS[docType] ?? docType
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="cases" />
        <main className="max-w-2xl w-full mx-auto px-6 py-20 text-center flex flex-col items-center justify-center gap-3">
          <Loader2Icon className="size-8 text-primary animate-spin" />
          <p className="text-sm text-slate-600 font-medium">{t.loading_form}</p>
        </main>
      </div>
    )
  }

  if (isError || !formData) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="cases" />
        <main className="max-w-2xl w-full mx-auto px-6 py-16 text-center">
          <h1 className="text-lg font-bold text-slate-800">{t.form_not_found}</h1>
          <Link
            to={caseId ? `/cases/${caseId}` : "/cases"}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:underline mt-4"
          >
            <ChevronLeftIcon className="w-4 h-4" />
            {t.back_to_case}
          </Link>
        </main>
      </div>
    )
  }

  const { form, fields, counts, ready, case_number } = formData

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900 antialiased print:bg-white print:text-black">
      {/* Navigation bar (hidden in print) */}
      <div className="print:hidden">
        <Nav active="cases" />
      </div>

      {/* Embedded print stylesheet */}
      <style>{`
        @media print {
          nav, header, footer, .no-print {
            display: none !important;
          }
          body, html {
            background: #ffffff !important;
            color: #000000 !important;
          }
          .paper-form-container {
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            box-shadow: none !important;
            background: transparent !important;
          }
          .print-field-row {
            border-bottom: 1px solid #e2e8f0 !important;
            padding: 10px 0 !important;
            page-break-inside: avoid !important;
          }
          .print-field-label {
            font-size: 12pt !important;
            font-weight: 600 !important;
            color: #1e293b !important;
          }
          .print-field-value {
            font-size: 13pt !important;
            font-weight: 500 !important;
            color: #0f172a !important;
            margin-top: 4px !important;
          }
          .print-hide {
            display: none !important;
          }
        }
      `}</style>

      {/* Sticky Mobile/Desktop Action & Summary Bar */}
      <div className="no-print sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-2xs">
        <div className="max-w-[800px] w-full mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          {/* Back link */}
          <Link
            to={`/cases/${caseId}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 transition-colors"
          >
            <ChevronLeftIcon className="size-4" />
            <span>{t.back_to_case}</span>
          </Link>

          {/* Counts summary chip */}
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-semibold">
              <span className="size-1.5 rounded-full bg-emerald-600" />
              {counts.filled} {t.filled}
            </span>
            {counts.needs_attention > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-semibold">
                <span className="size-1.5 rounded-full bg-amber-600" />
                {counts.needs_attention} {t.needs_attention}
              </span>
            )}
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-[11px] font-semibold">
              <span className="size-1.5 rounded-full bg-slate-400" />
              {counts.to_fill} {t.for_you_to_fill}
            </span>
          </div>

          {/* Actions: Language & Print */}
          <div className="flex items-center gap-2">
            {availableLanguages.length > 0 && (
              <div className="flex items-center gap-1 bg-slate-100/90 border border-slate-200 rounded-lg px-2 py-1 text-xs">
                <GlobeIcon className="size-3.5 text-slate-500 shrink-0" />
                <select
                  value={currentLang}
                  onChange={(e) => setCurrentLang(e.target.value)}
                  className="bg-transparent border-none text-xs font-medium text-slate-700 focus:outline-hidden cursor-pointer"
                  aria-label="Form language"
                >
                  {availableLanguages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.native_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <Button
              type="button"
              onClick={() => window.print()}
              variant={ready ? "default" : "outline"}
              size="sm"
              className={cn(
                "h-8 px-3 text-xs font-semibold gap-1.5",
                !ready && "border-amber-300 text-amber-900 bg-amber-50 hover:bg-amber-100"
              )}
            >
              <PrinterIcon className="size-3.5" />
              <span>{ready ? t.print : t.print_draft}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Main Container */}
      <main className="flex-1 max-w-[800px] w-full mx-auto px-4 py-6 sm:py-8 flex flex-col gap-4">
        {/* Conflict Warning Banner when ready is false */}
        {!ready && (
          <div className="no-print p-4 rounded-xl border border-amber-300 bg-amber-50/90 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-950">
            <div className="flex items-start gap-2.5">
              <AlertTriangleIcon className="size-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-amber-900">{t.draft_banner}</p>
                <p className="text-[11px] text-amber-800 mt-0.5">
                  Pre-filling is incomplete for fields in conflict across documents.
                </p>
              </div>
            </div>
            <Link
              to={`/cases/${caseId}#findings`}
              className="inline-flex items-center gap-1 text-xs font-bold text-amber-900 hover:text-amber-950 underline self-start sm:self-center shrink-0"
            >
              <span>{t.review_conflicts}</span>
              <ExternalLinkIcon className="size-3" />
            </Link>
          </div>
        )}

        {/* Paper Form Card: Centered single column (max width 720px), generous spacing */}
        <div className="paper-form-container max-w-[720px] w-full mx-auto bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 sm:p-10 flex flex-col gap-8">
          {/* Paper Form Header */}
          <div className="border-b border-slate-200 pb-6 flex flex-col gap-2 text-center sm:text-left">
            <div className="flex items-center justify-between flex-wrap gap-2 text-xs text-slate-400 font-mono">
              <span>{t.case_label}: {case_number}</span>
              {!ready && (
                <span className="print:hidden px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                  DRAFT
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {form.title}
            </h1>
            {form.description && (
              <p className="text-sm text-slate-500 leading-relaxed max-w-2xl">
                {form.description}
              </p>
            )}
          </div>

          {/* Form Fields: One by one with generous spacing */}
          <div className="flex flex-col gap-6">
            {fields.map((field) => {
              return (
                <FormFieldItem
                  key={field.key}
                  field={field}
                  userValue={userInputs[field.key] ?? ""}
                  onUserChange={(val) => handleInputChange(field.key, val)}
                  docTypeLabel={getDocTypeLabel(field.source_document_type)}
                  caseId={caseId!}
                  t={t}
                />
              )
            })}
          </div>
        </div>
      </main>
    </div>
  )
}

interface FormFieldItemProps {
  field: PrefilledFormField
  userValue: string
  onUserChange: (val: string) => void
  docTypeLabel: string
  caseId: string
  t: Record<string, string>
}

function FormFieldItem({
  field,
  userValue,
  onUserChange,
  docTypeLabel,
  caseId,
  t,
}: FormFieldItemProps) {
  const isFilled = field.status === "filled"
  const isNeedsAttention = field.status === "needs_attention"
  const isToFill = field.status === "to_fill"

  // Value for display
  const effectiveValue = isFilled
    ? field.display_value || String(field.value ?? "")
    : userValue

  return (
    <div className="print-field-row flex flex-col gap-1.5">
      {/* Label & Status Indicators */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <label className="print-field-label text-sm font-semibold text-slate-800 flex items-center gap-1">
          <span>{field.label}</span>
          {field.required && <span className="text-red-500 font-bold">*</span>}
        </label>

        {/* Source tag & lock icon for filled fields (hidden in print) */}
        {isFilled && (
          <div className="print-hide flex items-center gap-1.5">
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200/80"
              title={field.source_document_filename ?? undefined}
            >
              <LockIcon className="size-3 text-slate-400" />
              <span>
                {t.from} {docTypeLabel}
              </span>
            </span>
            <span
              className="text-slate-400 hover:text-slate-600 cursor-help"
              title={t.why_cant_edit}
            >
              <HelpCircleIcon className="size-3.5" />
            </span>
          </div>
        )}
      </div>

      {/* Field Input Widget based on type & status */}
      <div className="relative">
        {/* Clean print presentation (renders pure text lines during print) */}
        <div className="hidden print:block print-field-value">
          {effectiveValue || (
            <span className="text-slate-300 italic font-mono text-xs">_____________________</span>
          )}
        </div>

        {/* Screen interactive/read-only input (hidden during print) */}
        <div className="print:hidden">
          {isFilled ? (
            /* Read-only filled field with subtle lock state */
            <div
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-slate-50/80 text-slate-900 text-sm font-medium cursor-not-allowed flex items-center justify-between gap-2 select-all shadow-2xs"
              title={t.why_cant_edit}
            >
              <span className="truncate">{effectiveValue}</span>
              <LockIcon className="size-3.5 text-slate-400 shrink-0" />
            </div>
          ) : isNeedsAttention ? (
            /* Disputed field needing attention: empty, amber border */
            <div className="flex flex-col gap-1.5">
              <input
                type="text"
                disabled
                placeholder="—"
                className="w-full px-3.5 py-2.5 rounded-xl border-2 border-amber-400 bg-amber-50/20 text-slate-400 text-sm italic cursor-not-allowed shadow-2xs"
              />
            </div>
          ) : (
            /* To-fill field: applicant inputs data */
            <div>
              {field.type === "textarea" ? (
                <textarea
                  rows={3}
                  value={userValue}
                  onChange={(e) => onUserChange(e.target.value)}
                  placeholder={field.label}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs transition-all"
                />
              ) : field.type === "select" ? (
                <select
                  value={userValue}
                  onChange={(e) => onUserChange(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs transition-all cursor-pointer"
                >
                  <option value="">{t.select_placeholder}</option>
                  {(field.options ?? []).map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "date" ? (
                <input
                  type="date"
                  value={userValue}
                  onChange={(e) => onUserChange(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs transition-all"
                />
              ) : field.type === "number" ? (
                <input
                  type="number"
                  value={userValue}
                  onChange={(e) => onUserChange(e.target.value)}
                  placeholder={field.label}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs transition-all"
                />
              ) : (
                <input
                  type="text"
                  value={userValue}
                  onChange={(e) => onUserChange(e.target.value)}
                  placeholder={field.label}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary shadow-2xs transition-all"
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Underneath notes & links (hidden in print) */}
      <div className="print-hide">
        {isNeedsAttention && (
          <div className="flex flex-wrap items-center justify-between gap-2 mt-1">
            {field.note && (
              <p className="text-xs font-medium text-amber-800 leading-snug">
                {field.note}
              </p>
            )}
            <Link
              to={`/cases/${caseId}#findings`}
              className="text-xs font-bold text-amber-900 hover:text-amber-950 underline inline-flex items-center gap-1 ml-auto"
            >
              <span>{t.see_conflict}</span>
              <ExternalLinkIcon className="size-3" />
            </Link>
          </div>
        )}

        {isToFill && field.note && (
          <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
            {field.note}
          </p>
        )}
      </div>
    </div>
  )
}
