import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CreditCardIcon,
  ExternalLinkIcon,
  HelpCircleIcon,
  Loader2Icon,
  MapPinIcon,
  RotateCcwIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "lucide-react"

import { chooseProfileValue } from "@/api/profiles"
import { Button } from "@/components/ui/button"
import {
  DOCUMENT_TYPE_LABELS,
  IDENTITY_FIELD_LABELS,
  type CaseDetailDocument,
  type CaseProfile,
  type I18nCatalog,
} from "@/types/case"
import { cn } from "@/lib/utils"

interface VerifiedProfilePanelProps {
  profile: CaseProfile | null
  isLoading?: boolean
  caseId: string
  canAct?: boolean
  caseStatus?: string
  documents: CaseDetailDocument[]
  catalog?: I18nCatalog | null
  currentLang?: string
  token: string | null
}

const PROFILE_I18N: Record<string, Record<string, string>> = {
  en: {
    verified_profile: "Verified person profile",
    consolidated_truth: "Consolidated truth from all verified documents across the bundle.",
    reading_documents: "Still reading the documents…",
    profile_ready: "Profile ready",
    details_need_settled: "details need to be settled",
    detail_needs_settled: "detail needs to be settled",
    agreed: "Agreed",
    chosen_by_reviewer: "Chosen by reviewer",
    conflict: "Conflict",
    missing: "Missing",
    not_on_any_document: "Not on any document",
    docs_do_not_agree: "Documents do not agree",
    most_docs_agree: "Most documents agree",
    likely_needs_correction: "Likely needs correction:",
    use_this: "Use this",
    change: "Change",
    remove_choice: "Remove choice",
    select_different: "Select a different document for this detail:",
    credentials_and_postal: "Identity credentials & postal code",
    postal_code: "Postal code",
    see_conflict: "See conflict in findings",
    from: "from",
  },
  hi: {
    verified_profile: "सत्यापित व्यक्ति प्रोफ़ाइल",
    consolidated_truth: "सभी सत्यापित दस्तावेज़ों से संकलित विवरण।",
    reading_documents: "दस्तावेज़ अभी पढ़े जा रहे हैं…",
    profile_ready: "प्रोफ़ाइल तैयार है",
    details_need_settled: "विवरणों को सुलझाना आवश्यक है",
    detail_needs_settled: "विवरण को सुलझाना आवश्यक है",
    agreed: "सत्यापित",
    chosen_by_reviewer: "समीक्षक द्वारा चुना गया",
    conflict: "विरोधाभास",
    missing: "अनुपलब्ध",
    not_on_any_document: "किसी भी दस्तावेज़ में नहीं",
    docs_do_not_agree: "दस्तावेज़ों में सहमति नहीं है",
    most_docs_agree: "अधिकांश दस्तावेज़ सहमत हैं",
    likely_needs_correction: "संशोधन की आवश्यकता:",
    use_this: "इसे चुनें",
    change: "बदलें",
    remove_choice: "विकल्प हटाएं",
    select_different: "इस विवरण के लिए दूसरा दस्तावेज़ चुनें:",
    credentials_and_postal: "पहचान प्रमाण पत्र और पिन कोड",
    postal_code: "पिन कोड",
    see_conflict: "निष्कर्षों में विवाद देखें",
    from: "स्रोत:",
  },
}

export function VerifiedProfilePanel({
  profile,
  isLoading = false,
  caseId,
  canAct = false,
  caseStatus,
  documents,
  catalog,
  currentLang = "en",
  token,
}: VerifiedProfilePanelProps) {
  const queryClient = useQueryClient()
  const [expandedChosen, setExpandedChosen] = React.useState<Record<string, boolean>>({})
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = PROFILE_I18N[langKey] ?? PROFILE_I18N.en

  const isCaseDecided =
    caseStatus === "approved" || caseStatus === "rejected" || caseStatus === "closed"
  const canReview = Boolean(canAct && !isCaseDecided && token && caseId)

  const chooseMutation = useMutation({
    mutationFn: async ({
      fieldName,
      documentId,
    }: {
      fieldName: string
      documentId: string | null
    }) => {
      if (!token) throw new Error("Missing auth token")
      setErrorMessage(null)
      return chooseProfileValue(caseId, fieldName, documentId, token)
    },
    onSuccess: (updatedProfile) => {
      // Update local query cache immediately
      queryClient.setQueryData(["caseProfile", caseId, token], updatedProfile)
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ["caseProfile", caseId] })
      queryClient.invalidateQueries({ queryKey: ["case", caseId] })
      queryClient.invalidateQueries({ queryKey: ["formsList"] })
      queryClient.invalidateQueries({ queryKey: ["prefilledForm", caseId] })
    },
    onError: (err: Error) => {
      setErrorMessage(err.message || "Failed to update profile choice")
    },
  })

  // Helper to map document ID to localized document label
  const getDocNameById = (docId: string): string => {
    const doc = documents.find((d) => d.id === docId || d.original_filename === docId)
    const docType = doc?.document_type
    if (docType) {
      return (
        catalog?.documents?.[docType] ??
        DOCUMENT_TYPE_LABELS[docType] ??
        docType
      )
    }

    // Match synthetic filenames from test bundles (e.g. 03-degree-certificate.pdf)
    const idLower = docId.toLowerCase()
    if (idLower.includes("degree-certificate") || idLower.includes("degree_certificate")) {
      return catalog?.documents?.["degree_certificate"] ?? DOCUMENT_TYPE_LABELS["degree_certificate"] ?? "Degree certificate"
    }
    if (idLower.includes("national-id") || idLower.includes("national_id")) {
      return catalog?.documents?.["national_id_card"] ?? DOCUMENT_TYPE_LABELS["national_id_card"] ?? "Identity card"
    }
    if (idLower.includes("tax-id") || idLower.includes("tax_id") || idLower.includes("pan")) {
      return catalog?.documents?.["tax_id_card"] ?? DOCUMENT_TYPE_LABELS["tax_id_card"] ?? "Tax card"
    }
    if (idLower.includes("voter")) {
      return catalog?.documents?.["voter_id_card"] ?? DOCUMENT_TYPE_LABELS["voter_id_card"] ?? "Voter card"
    }
    if (idLower.includes("income")) {
      return catalog?.documents?.["income_certificate"] ?? DOCUMENT_TYPE_LABELS["income_certificate"] ?? "Income certificate"
    }
    if (idLower.includes("marksheet")) {
      return catalog?.documents?.["marksheet"] ?? DOCUMENT_TYPE_LABELS["marksheet"] ?? "Marksheet"
    }
    if (idLower.includes("passport")) {
      return catalog?.documents?.["passport"] ?? DOCUMENT_TYPE_LABELS["passport"] ?? "Passport"
    }
    if (idLower.includes("address")) {
      return catalog?.documents?.["address_proof"] ?? DOCUMENT_TYPE_LABELS["address_proof"] ?? "Address proof"
    }

    return doc?.original_filename ?? docId
  }

  const getDocTypeLabel = (docType: string | null | undefined): string => {
    if (!docType) return "Document"
    return catalog?.documents?.[docType] ?? DOCUMENT_TYPE_LABELS[docType] ?? docType
  }

  if (isLoading || !profile) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans">
        <div className="flex items-center justify-between pb-3.5 border-b border-border/80">
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="size-4.5 text-primary" />
            <span className="text-sm font-bold text-foreground">{t.verified_profile}</span>
          </div>
          <Loader2Icon className="size-4 text-muted-foreground animate-spin" />
        </div>
        <p className="text-xs text-muted-foreground">Loading verified person profile…</p>
      </div>
    )
  }

  const { fields, counts, ready, checks_complete, postal_code, id_numbers } = profile

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pb-3.5 border-b border-border/80">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="size-4.5 text-primary" />
            <h3 className="text-sm font-bold text-foreground">{t.verified_profile}</h3>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {t.consolidated_truth}
          </p>
        </div>

        {/* Readiness Chip */}
        {!checks_complete ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Loader2Icon className="size-3 animate-spin" />
            {t.reading_documents}
          </span>
        ) : ready ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2Icon className="size-3.5 text-emerald-600" />
            {t.profile_ready}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-800 border border-red-200">
            <AlertTriangleIcon className="size-3.5 text-red-600" />
            {counts.conflict} {counts.conflict === 1 ? t.detail_needs_settled : t.details_need_settled}
          </span>
        )}
      </div>

      {/* Global Mutation Error */}
      {errorMessage && (
        <div className="p-2.5 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive flex items-center justify-between">
          <span>{errorMessage}</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setErrorMessage(null)}
            className="h-6 text-[11px]"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Fields List */}
      <div className="divide-y divide-border/60">
        {fields.map((field) => {
          const fieldLabel =
            catalog?.fields?.[field.field] ?? IDENTITY_FIELD_LABELS[field.field] ?? field.label
          const docTypeLabel = getDocTypeLabel(field.document_type)
          const isChosen = field.status === "chosen"
          const isConflict = field.status === "conflict"
          const isAgreed = field.status === "agreed"
          const isMissing = field.status === "missing"
          const isExpanded = Boolean(expandedChosen[field.field])

          return (
            <div key={field.field} className="py-3 flex flex-col gap-1.5 text-xs">
              {/* Field Label + Status Tag */}
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-muted-foreground">{fieldLabel}</span>

                <div className="flex items-center gap-1.5">
                  {isAgreed && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                      <CheckCircle2Icon className="size-3.5 text-emerald-600" />
                      {t.agreed}
                    </span>
                  )}

                  {isChosen && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                      <SparklesIcon className="size-2.5" />
                      {t.chosen_by_reviewer}
                    </span>
                  )}

                  {isConflict && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-600">
                      <AlertTriangleIcon className="size-3.5 text-red-500" />
                      {t.conflict}
                    </span>
                  )}

                  {isMissing && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                      <HelpCircleIcon className="size-3 text-muted-foreground/60" />
                      {t.missing}
                    </span>
                  )}
                </div>
              </div>

              {/* Status Content */}
              {(isAgreed || isChosen) && (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-col gap-0.5">
                    <div className="text-sm font-bold text-foreground flex items-center gap-1.5">
                      <span>{field.display_value || String(field.value ?? "")}</span>
                      {isAgreed && <CheckCircle2Icon className="size-4 text-emerald-600 shrink-0 inline" />}
                      {field.latin && field.latin !== field.value && (
                        <span className="text-xs font-normal text-muted-foreground">
                          ({field.latin})
                        </span>
                      )}
                    </div>
                    {(field.document_type || field.document_filename) && (
                      <span
                        className="text-[11px] text-muted-foreground"
                        title={field.document_filename ?? undefined}
                      >
                        {t.from} <span className="font-medium text-foreground/80">{docTypeLabel}</span>
                      </span>
                    )}
                  </div>

                  {/* Reviewer Action on Chosen Row */}
                  {isChosen && canReview && (
                    <div className="flex items-center gap-1.5">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setExpandedChosen((prev) => ({
                            ...prev,
                            [field.field]: !prev[field.field],
                          }))
                        }
                        className="h-7 text-[11px] font-medium"
                      >
                        {isExpanded ? "Close" : t.change}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={chooseMutation.isPending}
                        onClick={() =>
                          chooseMutation.mutate({ fieldName: field.field, documentId: null })
                        }
                        className="h-7 text-[11px] text-muted-foreground hover:text-destructive gap-1"
                      >
                        <RotateCcwIcon className="size-3" />
                        {t.remove_choice}
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Conflict State */}
              {isConflict && (
                <div className="flex flex-col gap-2 mt-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-bold text-red-700 flex items-center gap-1.5">
                      <AlertTriangleIcon className="size-3.5 text-red-600 shrink-0" />
                      {t.docs_do_not_agree}
                    </p>

                    <a
                      href={`#finding-${field.field}`}
                      onClick={(e) => {
                        e.preventDefault()
                        const el =
                          document.getElementById(`finding-${field.field}`) ||
                          document.getElementById("findings-panel")
                        el?.scrollIntoView({ behavior: "smooth" })
                      }}
                      className="text-[11px] text-amber-700 hover:text-amber-900 hover:underline inline-flex items-center gap-1 font-medium"
                    >
                      <ExternalLinkIcon className="size-3" />
                      {t.see_conflict}
                    </a>
                  </div>

                  {/* Candidates List as Chips */}
                  <div className="flex flex-col gap-1.5">
                    {field.candidates.map((candidate, idx) => {
                      const docNames = candidate.document_ids.map(getDocNameById)
                      const isSuggested = field.suggested_document_id === candidate.document_id

                      return (
                        <div
                          key={idx}
                          className={cn(
                            "flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg border text-xs",
                            isSuggested
                              ? "bg-emerald-50/70 border-emerald-300 text-emerald-950"
                              : "bg-muted/40 border-border/80 text-foreground"
                          )}
                        >
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-bold">
                              {candidate.display_value || String(candidate.value ?? "")}
                            </span>
                            <span className="text-muted-foreground text-[11px]">
                              — {docNames.join(", ")}
                            </span>
                            {isSuggested && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-200/90 text-emerald-900">
                                {t.most_docs_agree}
                              </span>
                            )}
                          </div>

                          {canReview && (
                            <Button
                              type="button"
                              size="sm"
                              disabled={chooseMutation.isPending}
                              onClick={() =>
                                chooseMutation.mutate({
                                  fieldName: field.field,
                                  documentId: candidate.document_id,
                                })
                              }
                              className={cn(
                                "h-6 text-[11px] px-2.5 font-semibold rounded-md",
                                isSuggested
                                  ? "bg-emerald-700 hover:bg-emerald-800 text-white"
                                  : "bg-primary hover:bg-primary/90 text-primary-foreground"
                              )}
                            >
                              {t.use_this}
                            </Button>
                          )}
                        </div>
                      )
                    })}
                  </div>

                  {/* Likely needs correction line */}
                  {field.documents_to_correct && field.documents_to_correct.length > 0 && (
                    <div className="rounded-md bg-amber-50/80 border border-amber-200/80 px-2.5 py-1 text-[11px] text-amber-900 leading-snug">
                      <span className="font-semibold text-amber-950">{t.likely_needs_correction}</span>{" "}
                      {field.documents_to_correct.map(getDocNameById).join(", ")}
                    </div>
                  )}
                </div>
              )}

              {/* Chosen Field Reopen Candidates */}
              {isChosen && isExpanded && canReview && (
                <div className="flex flex-col gap-1.5 p-2.5 mt-1 rounded-lg bg-muted/30 border border-border/80 animate-in fade-in duration-150">
                  <span className="text-[11px] font-semibold text-muted-foreground">
                    {t.select_different}
                  </span>
                  <div className="flex flex-col gap-1.5">
                    {field.candidates.map((candidate, idx) => {
                      const docNames = candidate.document_ids.map(getDocNameById)
                      const isCurrentChoice = candidate.document_id === field.document_id

                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-2 p-1.5 rounded bg-background border border-border/60 text-xs"
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold">
                              {candidate.display_value || String(candidate.value ?? "")}
                            </span>
                            <span className="text-muted-foreground text-[11px]">
                              — {docNames.join(", ")}
                            </span>
                            {isCurrentChoice && (
                              <span className="px-1 text-[10px] font-bold text-blue-700 bg-blue-50 rounded">
                                Current
                              </span>
                            )}
                          </div>

                          {!isCurrentChoice && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={chooseMutation.isPending}
                              onClick={() => {
                                chooseMutation.mutate({
                                  fieldName: field.field,
                                  documentId: candidate.document_id,
                                })
                                setExpandedChosen((prev) => ({ ...prev, [field.field]: false }))
                              }}
                              className="h-6 text-[10px] px-2"
                            >
                              {t.use_this}
                            </Button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Missing State */}
              {isMissing && (
                <p className="text-xs text-muted-foreground italic">{t.not_on_any_document}</p>
              )}
            </div>
          )
        })}
      </div>

      {/* Secondary Block: Postal Code & ID Numbers */}
      {(postal_code || (id_numbers && Object.keys(id_numbers).length > 0)) && (
        <div className="mt-1 pt-3 border-t border-border/80 flex flex-col gap-2.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            {t.credentials_and_postal}
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {postal_code && (
              <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/50">
                <MapPinIcon className="size-3.5 text-muted-foreground shrink-0" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground">{t.postal_code}</span>
                  <span className="font-mono font-semibold text-foreground">{postal_code}</span>
                </div>
              </div>
            )}

            {id_numbers &&
              Object.entries(id_numbers).map(([docType, idInfo]) => {
                const label = getDocTypeLabel(docType)
                return (
                  <div
                    key={docType}
                    className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/50"
                  >
                    <CreditCardIcon className="size-3.5 text-muted-foreground shrink-0" />
                    <div className="flex flex-col min-w-0">
                      <span className="text-[10px] text-muted-foreground truncate">{label}</span>
                      <span className="font-mono font-semibold text-foreground truncate">
                        {idInfo.display_value || idInfo.value}
                      </span>
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}
