import { apiFetch } from "@/api/client"
import type {
  FamilyCreatePayload,
  FamilyView,
  MemberCreatePayload,
  MemberUpdatePayload,
} from "@/types/family"

/**
 * Get the current user's family view, or null if they haven't set one up yet.
 * GET /family?lang=<code>
 */
export function getMyFamily(lang = "en", token: string): Promise<FamilyView | null> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView | null>(`/family${query}`, { token })
}

/**
 * Set up the caller's family with caller as head (relation 'self').
 * POST /family?lang=<code>
 */
export function createFamily(
  payload: FamilyCreatePayload,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView>(`/family${query}`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  })
}

/**
 * Add a member to the caller's family.
 * POST /family/members?lang=<code>
 */
export function addFamilyMember(
  payload: MemberCreatePayload,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView>(`/family/members${query}`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  })
}

/**
 * Correct a member's details.
 * PATCH /family/members/{id}?lang=<code>
 */
export function updateFamilyMember(
  memberId: string,
  payload: MemberUpdatePayload,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView>(`/family/members/${memberId}${query}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  })
}

/**
 * Remove a member added by mistake.
 * DELETE /family/members/{id}?lang=<code>
 */
export function removeFamilyMember(
  memberId: string,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView>(`/family/members/${memberId}${query}`, {
    method: "DELETE",
    token,
  })
}

/**
 * Get a specific family view by family ID (accessible by head or company reviewer).
 * GET /families/{family_id}?lang=<code>
 */
export function getFamilyById(
  familyId: string,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : ""
  return apiFetch<FamilyView>(`/families/${familyId}${query}`, { token })
}
