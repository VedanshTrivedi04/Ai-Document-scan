import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { PenLine } from "lucide-react"

import { clearSignatureReference, setSignatureReference } from "@/api/cases"
import type { CaseDetailDocument } from "@/types/case"

interface Props {
  caseId: string
  token: string
  canAct: boolean
  documents: CaseDetailDocument[]
  activeDoc: CaseDetailDocument | undefined
  referenceDocumentId: string | null | undefined
}

function signatureCount(doc: CaseDetailDocument | undefined): number {
  const fields = doc?.extracted_fields
  if (!fields || fields.schema !== "identity") return 0
  return fields.signatures?.items?.length ?? 0
}

/**
 * Lets a reviewer pick the document whose signature every other document is
 * compared with. Shown above the document viewer of an identity case. The
 * comparison runs in the background, so the case is reloaded for a while after
 * the choice.
 */
export function SignatureReferenceBar({ caseId, token, canAct, documents, activeDoc, referenceDocumentId }: Props) {
  const queryClient = useQueryClient()
  const [error, setError] = React.useState<string | null>(null)
  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: ["case", caseId] })
    // the comparison finishes a moment after the request
    for (const delay of [2500, 6000, 12000]) {
      window.setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["case", caseId] }), delay)
    }
  }
  const choose = useMutation({
    mutationFn: (documentId: string) => setSignatureReference(caseId, documentId, token),
    onSuccess: () => {
      setError(null)
      reload()
    },
    onError: (e: Error) => setError(e.message),
  })
  const clear = useMutation({
    mutationFn: () => clearSignatureReference(caseId, token),
    onSuccess: () => {
      setError(null)
      reload()
    },
    onError: (e: Error) => setError(e.message),
  })

  const anySignature = documents.some((d) => signatureCount(d) > 0)
  if (!anySignature && !referenceDocumentId) return null

  const reference = documents.find((d) => d.id === referenceDocumentId)
  const activeHasSignature = signatureCount(activeDoc) > 0
  const activeIsReference = !!activeDoc && activeDoc.id === referenceDocumentId

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-3 shadow-2xs flex flex-wrap items-center gap-3">
      <PenLine className="size-4 text-slate-500 shrink-0" />
      <div className="min-w-0 flex-1 text-xs">
        {reference ? (
          <span className="text-slate-700">
            Reference signature: <b>{reference.original_filename}</b>. Every other document's signature is compared
            with it.
          </span>
        ) : (
          <span className="text-slate-600">
            Signatures were found. Choose a document as the reference and the others are compared with it.
          </span>
        )}
        {error && <span className="block text-red-600 mt-1">{error}</span>}
      </div>
      {canAct && activeDoc && !activeIsReference && activeHasSignature && (
        <button
          type="button"
          disabled={choose.isPending}
          onClick={() => choose.mutate(activeDoc.id)}
          className="text-xs font-semibold rounded-md bg-primary text-primary-foreground px-3 py-1.5 disabled:opacity-60"
        >
          {choose.isPending ? "Comparing..." : "Use this document's signature as reference"}
        </button>
      )}
      {canAct && activeDoc && !activeIsReference && !activeHasSignature && !reference && (
        <span className="text-[11px] text-slate-500">No signature found on this document.</span>
      )}
      {canAct && reference && (
        <button
          type="button"
          disabled={clear.isPending}
          onClick={() => clear.mutate()}
          className="text-xs font-semibold rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 disabled:opacity-60"
        >
          Stop comparing
        </button>
      )}
    </div>
  )
}
