import { apiFetch } from "@/api/client"

export interface OrganisationInfo {
  subdomain: string | null
  name: string | null
  base_domain: string | null
}

/**
 * Fetch the current organisation for this host.
 * No auth token needed.
 * Returns 404 if no active organisation uses this subdomain.
 * On platform's own site: subdomain and name are null.
 */
export function getOrganisation(subdomain?: string | null): Promise<OrganisationInfo> {
  const query = subdomain ? `?subdomain=${encodeURIComponent(subdomain)}` : ""
  return apiFetch<OrganisationInfo>(`/organisation${query}`)
}
