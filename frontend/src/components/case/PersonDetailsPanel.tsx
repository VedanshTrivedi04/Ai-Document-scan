import { AlertCircleIcon, MapPinOffIcon } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { BoundingBox, I18nCatalog, IdentityExtractedFields } from "@/types/case"

interface PersonDetailsPanelProps {
  extractedFields: IdentityExtractedFields | null
  processingStatus?: string
  processingError?: string | null
  selectedBox?: BoundingBox | null
  onSelectField?: (box: BoundingBox | null) => void
  catalog?: I18nCatalog | null
}

/** Format YYYY-MM-DD into "12 April 1991" */
function formatDate(isoDate: string | null | undefined): string | null {
  if (!isoDate) return null
  const parts = isoDate.split("-")
  if (parts.length !== 3) return isoDate
  const year = parseInt(parts[0], 10)
  const month = parseInt(parts[1], 10) - 1
  const day = parseInt(parts[2], 10)
  const d = new Date(year, month, day)
  if (isNaN(d.getTime())) return isoDate
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  })
}

/** Format annual income into "INR 1,20,000" using Indian numbering format or currency prefix */
function formatIncome(amount: number | null | undefined, currency: string | null | undefined): string | null {
  if (amount === null || amount === undefined) return null
  const curr = currency || "INR"
  try {
    const formatted = new Intl.NumberFormat("en-IN").format(amount)
    return `${curr} ${formatted}`
  } catch {
    return `${curr} ${amount.toLocaleString()}`
  }
}

export function PersonDetailsPanel({
  extractedFields,
  processingStatus,
  processingError,
  selectedBox,
  onSelectField,
  catalog,
}: PersonDetailsPanelProps) {
  if (!extractedFields) {
    if (processingStatus === "failed") {
      return (
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-5 text-center text-xs text-destructive">
          <p className="font-semibold">Extraction failed</p>
          <p className="mt-1 text-muted-foreground">{processingError || "Could not process document fields."}</p>
        </div>
      )
    }

    return (
      <div className="rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="flex items-center justify-between pb-3 border-b border-border/80 mb-4">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-1.5 py-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-5 w-48" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const fields = extractedFields.identity_fields

  const rows: Array<{
    id: string
    label: string
    value: string | null
    latin?: string | null
    uncertain?: boolean
    boundingBox?: BoundingBox
  }> = [
    {
      id: "full_name",
      label: catalog?.fields?.full_name ?? "Name",
      value: fields?.full_name?.value ?? null,
      latin: fields?.full_name?.latin ?? null,
      uncertain: fields?.full_name?.uncertain,
      boundingBox: fields?.full_name?.bounding_box,
    },
    {
      id: "parent_or_spouse_name",
      label: catalog?.fields?.parent_or_spouse_name ?? "Parent / spouse name",
      value: fields?.parent_or_spouse_name?.value ?? null,
      latin: fields?.parent_or_spouse_name?.latin ?? null,
      uncertain: fields?.parent_or_spouse_name?.uncertain,
      boundingBox: fields?.parent_or_spouse_name?.bounding_box,
    },
    {
      id: "date_of_birth",
      label: catalog?.fields?.date_of_birth ?? "Date of birth",
      value: formatDate(fields?.date_of_birth?.value) ?? fields?.date_of_birth?.raw_text ?? null,
      uncertain: fields?.date_of_birth?.uncertain,
      boundingBox: fields?.date_of_birth?.bounding_box,
    },
    {
      id: "gender",
      label: catalog?.fields?.gender ?? "Gender",
      value: fields?.gender?.value
        ? fields.gender.value.charAt(0).toUpperCase() + fields.gender.value.slice(1)
        : fields?.gender?.raw_text ?? null,
      uncertain: fields?.gender?.uncertain,
      boundingBox: fields?.gender?.bounding_box,
    },
    {
      id: "address",
      label: catalog?.fields?.address ?? "Address",
      value: fields?.address?.value ?? null,
      latin: fields?.address?.latin ?? null,
      uncertain: fields?.address?.uncertain,
      boundingBox: fields?.address?.bounding_box,
    },
    {
      id: "id_number",
      label: catalog?.fields?.id_number ?? "ID number",
      value: fields?.id_number?.value ?? null,
      uncertain: fields?.id_number?.uncertain,
      boundingBox: fields?.id_number?.bounding_box,
    },
    {
      id: "annual_income",
      label: catalog?.fields?.annual_income ?? "Annual income",
      value: formatIncome(fields?.annual_income?.value, fields?.annual_income?.currency) ?? fields?.annual_income?.raw_text ?? null,
      uncertain: fields?.annual_income?.uncertain,
      boundingBox: fields?.annual_income?.bounding_box,
    },
    {
      id: "issuing_authority",
      label: catalog?.fields?.issuing_authority ?? "Issued by",
      value: fields?.issuing_authority?.value ?? null,
      uncertain: fields?.issuing_authority?.uncertain,
      boundingBox: fields?.issuing_authority?.bounding_box,
    },
    {
      id: "issue_date",
      label: catalog?.fields?.issue_date ?? "Issue date",
      value: formatDate(fields?.issue_date?.value) ?? fields?.issue_date?.raw_text ?? null,
      uncertain: fields?.issue_date?.uncertain,
      boundingBox: fields?.issue_date?.bounding_box,
    },
  ]

  const isBoxEqual = (b1?: BoundingBox | null, b2?: BoundingBox | null) => {
    if (!b1 || !b2) return false
    return b1.page === b2.page && b1.x === b2.x && b1.y === b2.y && b1.width === b2.width && b1.height === b2.height
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col font-sans">
      <div className="flex items-center justify-between pb-3.5 border-b border-border/80 mb-3">
        <div>
          <h3 className="text-sm font-bold text-foreground">Person details</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">Click a field to locate on document</p>
        </div>
        {extractedFields.document_type_confidence != null && (
          <span className="text-[11px] font-mono text-muted-foreground">
            Match: {(extractedFields.document_type_confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      <div className="divide-y divide-border/60">
        {rows.map((row) => {
          const isSelected = isBoxEqual(selectedBox, row.boundingBox)
          const hasBox = Boolean(row.boundingBox)

          return (
            <div
              key={row.id}
              role={hasBox ? "button" : undefined}
              tabIndex={hasBox ? 0 : undefined}
              onClick={() => {
                if (hasBox && onSelectField) {
                  onSelectField(isSelected ? null : (row.boundingBox ?? null))
                }
              }}
              onKeyDown={(e) => {
                if (hasBox && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault()
                  onSelectField?.(isSelected ? null : (row.boundingBox ?? null))
                }
              }}
              className={cn(
                "group py-3 px-2 rounded-lg transition-colors flex flex-col gap-1",
                hasBox ? "cursor-pointer hover:bg-muted/40" : "cursor-default",
                isSelected && "bg-blue-50/80 border border-blue-200/90 text-blue-950"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {row.label}
                </span>
                <div className="flex items-center gap-1.5 shrink-0">
                  {row.uncertain && (
                    <span className="inline-flex items-center gap-1 rounded bg-amber-100 text-amber-800 border border-amber-200/80 px-1.5 py-0.5 text-[10px] font-medium">
                      <AlertCircleIcon className="size-3" />
                      Please check
                    </span>
                  )}
                  {!hasBox && row.value && (
                    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/80">
                      <MapPinOffIcon className="size-2.5 opacity-60" />
                      not located
                    </span>
                  )}
                </div>
              </div>

              {row.value ? (
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-foreground break-words leading-snug">
                    {row.value}
                  </span>
                  {row.latin && row.latin.trim() !== row.value.trim() && (
                    <span className="text-xs text-muted-foreground mt-0.5 font-medium">
                      {row.latin}
                    </span>
                  )}
                </div>
              ) : (
                <span className="text-xs italic text-muted-foreground/80">
                  Not on this document
                </span>
              )}
            </div>
          )
        })}
      </div>

      {extractedFields.additional_fields?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block mb-2.5">
            Additional details
          </span>
          <div className="space-y-2">
            {extractedFields.additional_fields.map((f, idx) => (
              <div key={idx} className="flex justify-between items-baseline gap-2 text-xs py-1">
                <span className="text-muted-foreground truncate">{f.field_name}</span>
                <span className="font-semibold text-foreground text-right">{f.value ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
