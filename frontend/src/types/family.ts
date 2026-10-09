export type FamilyMemberRelation =
  | "self"
  | "spouse"
  | "son"
  | "daughter"
  | "father"
  | "mother"
  | "other"

export interface FamilyMemberDocument {
  id: string
  filename: string
  document_type: string | null
  processing_status: string
}

export interface FamilyMemberCase {
  id: string
  case_number: string
  case_type: string
  status: string
  created_at: string
  document_count: number
  checks_complete: boolean
  open_conflicts: number
  documents: FamilyMemberDocument[]
}

/** The sign-in a head created for a member. */
export interface MemberLogin {
  email: string
  is_active: boolean
  must_change_password: boolean
}

/** Shown once, right after a sign-in is created or its password reset. */
export interface MemberCredentials {
  member_id: string
  email: string
  /** null when the head chose the password themselves. */
  temporary_password: string | null
}

export interface FamilyMember {
  id: string
  full_name: string
  relation: FamilyMemberRelation
  relation_label: string
  date_of_birth: string | null
  is_head: boolean
  has_login: boolean
  login: MemberLogin | null
  latest_case_id: string | null
  profile_ready: boolean | null
  cases: FamilyMemberCase[]
}

export type FamilyCheckResult = "match" | "conflict" | "not_checked"

export type FamilyCheckSeverity = "info" | "low" | "medium" | "high" | "critical"

export interface FamilyCheck {
  check: "member_identity" | "shared_address" | "parent_name" | "birth_order" | string
  label: string
  member_id: string
  member_name: string
  relation: string
  result: FamilyCheckResult
  severity: FamilyCheckSeverity
  summary: string
}

export interface FamilyCheckCounts {
  match: number
  conflict: number
  not_checked: number
}

export interface FamilyView {
  id: string
  name: string
  head_user_id: string
  language: string
  members: FamilyMember[]
  checks: FamilyCheck[]
  check_counts: FamilyCheckCounts
  /** Only on the response to creating a sign-in or resetting its password. */
  credentials?: MemberCredentials
}

export interface MemberLoginPayload {
  email: string
  /** Leave out to have a temporary password generated. */
  password?: string
}

export interface FamilyCreatePayload {
  name?: string
  head_date_of_birth?: string
}

export interface MemberCreatePayload {
  full_name: string
  relation: "spouse" | "son" | "daughter" | "father" | "mother" | "other"
  date_of_birth?: string | null
  login?: MemberLoginPayload
}

/** GET /family/me: what a member with a sign-in sees of the family. */
export interface MyMembership {
  member_id: string
  full_name: string
  relation: FamilyMemberRelation
  family_name: string
  latest_case_id: string | null
  profile_ready: boolean | null
  cases: {
    id: string
    case_number: string
    status: string
    created_at: string
    document_count: number
    open_conflicts: number
    documents: FamilyMemberDocument[]
  }[]
}

export type ComparisonResolution = "open" | "conflict_confirmed" | "no_issue"

export interface ComparisonCheck extends FamilyCheck {
  finding_id: string | null
  review_status: "pending" | "accepted" | "dismissed" | null
  review_note: string | null
  resolution: ComparisonResolution | null
  reviewed_by_name: string | null
  reviewed_at: string | null
}

export interface ComparisonMember {
  id: string
  full_name: string
  relation: FamilyMemberRelation
  relation_label: string
  is_head: boolean
  document_count: number
  profile_ready: boolean | null
}

export interface FamilyComparison {
  id: string
  case_number: string
  status: string
  created_at: string
  family_id: string
  family_name: string
  /** The caller heads this family (may run it again or close it). */
  is_head: boolean
  /** The caller may confirm or dismiss conflicts: the head or a company reviewer. */
  can_review: boolean
  language: string
  members: ComparisonMember[]
  checks: ComparisonCheck[]
  check_counts: FamilyCheckCounts
  finding_counts: Record<ComparisonResolution, number>
}

export interface ComparisonListItem {
  id: string
  case_number: string
  created_at: string
  members: string[]
  conflicts: number
  open_conflicts: number
}

export interface MemberUpdatePayload {
  full_name?: string
  relation?: "spouse" | "son" | "daughter" | "father" | "mother" | "other"
  date_of_birth?: string | null
}

export const RELATION_OPTIONS: { value: FamilyMemberRelation; label: string }[] = [
  { value: "spouse", label: "Spouse" },
  { value: "son", label: "Son" },
  { value: "daughter", label: "Daughter" },
  { value: "father", label: "Father" },
  { value: "mother", label: "Mother" },
  { value: "other", label: "Other" },
]
