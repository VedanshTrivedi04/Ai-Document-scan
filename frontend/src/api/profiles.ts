import { apiFetch } from "@/api/client"
import type {
  CaseProfile,
  FormTemplateSummary,
  PrefilledFormResponse,
} from "@/types/case"

/**
 * Verified profile of the person a case is about (Phase 6).
 * GET /cases/{id}/profile
 */
export function getCaseProfile(caseId: string, token: string): Promise<CaseProfile> {
  return apiFetch<CaseProfile>(`/cases/${caseId}/profile`, { token })
}

/**
 * Choose the right document for a disputed profile detail (or remove the choice).
 * PUT /cases/{id}/profile/{field} body: { document_id: string | null }
 */
export function chooseProfileValue(
  caseId: string,
  fieldName: string,
  documentId: string | null,
  token: string,
): Promise<CaseProfile> {
  return apiFetch<CaseProfile>(`/cases/${caseId}/profile/${fieldName}`, {
    method: "PUT",
    token,
    body: JSON.stringify({ document_id: documentId }),
  })
}

/**
 * List application forms available for pre-filling.
 * GET /forms?case_type=<case_type>&lang=<code>
 */
export function listForms(
  caseType?: string | null,
  lang = "en",
  token?: string,
): Promise<FormTemplateSummary[]> {
  const params = new URLSearchParams()
  if (caseType) params.set("case_type", caseType)
  if (lang) params.set("lang", lang)
  const query = params.toString()
  return apiFetch<FormTemplateSummary[]>(`/forms${query ? `?${query}` : ""}`, {
    token,
  })
}

/**
 * A form pre-filled from the case's verified profile.
 * GET /cases/{id}/forms/{form_id}?lang=<code>
 */
export function getPrefilledForm(
  caseId: string,
  formId: string,
  lang = "en",
  token: string,
): Promise<PrefilledFormResponse> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<PrefilledFormResponse>(`/cases/${caseId}/forms/${formId}${query}`, {
    token,
  })
}
