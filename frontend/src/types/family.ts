export type FamilyMemberRelation =
  | "self"
  | "spouse"
  | "son"
  | "daughter"
  | "father"
  | "mother"
  | "other"

export interface FamilyMemberCase {
  id: string
  case_number: string
  case_type: string
  status: string
  created_at: string
  document_count: number
  checks_complete: boolean
  open_conflicts: number
}

export interface FamilyMember {
  id: string
  full_name: string
  relation: FamilyMemberRelation
  relation_label: string
  date_of_birth: string | null
  is_head: boolean
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
}

export interface FamilyCreatePayload {
  name?: string
  head_date_of_birth?: string
}

export interface MemberCreatePayload {
  full_name: string
  relation: "spouse" | "son" | "daughter" | "father" | "mother" | "other"
  date_of_birth?: string | null
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
