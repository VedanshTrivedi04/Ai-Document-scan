import { apiFetch } from "@/api/client"
import type {
  ComparisonListItem,
  FamilyComparison,
  FamilyCreatePayload,
  FamilyView,
  MemberCreatePayload,
  MemberLoginPayload,
  MemberUpdatePayload,
  MyMembership,
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

function langQuery(lang: string): string {
  return lang ? `?lang=${encodeURIComponent(lang)}` : ""
}

/**
 * Create a sign-in for an existing member.
 * POST /family/members/{id}/login. The response carries `credentials` once.
 */
export function createMemberLogin(
  memberId: string,
  payload: MemberLoginPayload,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  return apiFetch<FamilyView>(`/family/members/${memberId}/login${langQuery(lang)}`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  })
}

/**
 * Reset a member's password to a temporary one (generated unless one is sent).
 * POST /family/members/{id}/login/reset-password
 */
export function resetMemberPassword(
  memberId: string,
  payload: { password?: string },
  lang = "en",
  token: string,
): Promise<FamilyView> {
  return apiFetch<FamilyView>(`/family/members/${memberId}/login/reset-password${langQuery(lang)}`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  })
}

/** Switch a member's sign-in on or off. PATCH /family/members/{id}/login */
export function setMemberLoginActive(
  memberId: string,
  isActive: boolean,
  lang = "en",
  token: string,
): Promise<FamilyView> {
  return apiFetch<FamilyView>(`/family/members/${memberId}/login${langQuery(lang)}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ is_active: isActive }),
  })
}

/** Remove a member's sign-in (the member and documents stay). DELETE /family/members/{id}/login */
export function removeMemberLogin(memberId: string, lang = "en", token: string): Promise<FamilyView> {
  return apiFetch<FamilyView>(`/family/members/${memberId}/login${langQuery(lang)}`, {
    method: "DELETE",
    token,
  })
}

/** What a member with a sign-in sees of the family, or null. GET /family/me */
export function getMyMembership(token: string): Promise<MyMembership | null> {
  return apiFetch<MyMembership | null>("/family/me", { token })
}

/** Compare members with the head. POST /family/comparisons */
export function createComparison(
  memberIds: string[],
  lang = "en",
  token: string,
): Promise<FamilyComparison> {
  return apiFetch<FamilyComparison>(`/family/comparisons${langQuery(lang)}`, {
    method: "POST",
    token,
    body: JSON.stringify({ member_ids: memberIds }),
  })
}

/** The head's comparisons, newest first. GET /family/comparisons */
export function listComparisons(token: string): Promise<ComparisonListItem[]> {
  return apiFetch<ComparisonListItem[]>("/family/comparisons", { token })
}

/** One comparison with its checks and decisions. GET /family/comparisons/{id} */
export function getComparison(id: string, lang = "en", token: string): Promise<FamilyComparison> {
  return apiFetch<FamilyComparison>(`/family/comparisons/${id}${langQuery(lang)}`, { token })
}

/** Run the checks again, keeping decisions. POST /family/comparisons/{id}/refresh */
export function refreshComparison(id: string, lang = "en", token: string): Promise<FamilyComparison> {
  return apiFetch<FamilyComparison>(`/family/comparisons/${id}/refresh${langQuery(lang)}`, {
    method: "POST",
    token,
  })
}

/** Close a comparison (drops it from the list). DELETE /family/comparisons/{id} */
export function closeComparison(id: string, token: string): Promise<void> {
  return apiFetch<void>(`/family/comparisons/${id}`, { method: "DELETE", token })
}

/** Accept or dismiss a finding. PATCH /cases/{caseId}/findings/{findingId} */
export function reviewFinding(
  caseId: string,
  findingId: string,
  decision: "accepted" | "dismissed" | "pending",
  note: string | undefined,
  token: string,
): Promise<unknown> {
  return apiFetch<unknown>(`/cases/${caseId}/findings/${findingId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ decision, note: note || undefined }),
  })
}
