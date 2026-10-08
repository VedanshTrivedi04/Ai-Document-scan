import { apiFetch } from "@/api/client"
import type { I18nCatalog, LanguageInfo } from "@/types/case"

/**
 * Lists the languages the interface is offered in and whether each is available.
 * No authentication token needed.
 */
export function getLanguages(): Promise<LanguageInfo[]> {
  return apiFetch<LanguageInfo[]>("/i18n/languages")
}

/**
 * Returns localized label maps for fields, documents, severities, reasons, and actions.
 * Keyed by machine keys. Requires authentication token.
 */
export function getCatalog(lang: string, token: string): Promise<I18nCatalog> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<I18nCatalog>(`/i18n/catalog${query}`, { token })
}
