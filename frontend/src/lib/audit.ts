/**
 * Audit event label and tone helpers.
 *
 * Shared between:
 *  - src/types/case.ts   (re-exports AUDIT_EVENT_LABELS)
 *  - ActivityTimeline    (case-level audit trail)
 *  - AuditHistoryPage    (platform-wide audit history)
 */

export type AuditTone = "rose" | "emerald" | "amber" | "blue" | "slate"

/** Human-readable labels for every audit event_type the backend emits. */
export const AUDIT_EVENT_LABELS: Record<string, string> = {
  // Case lifecycle
  case_created: "Case created",
  case_status_changed: "Status changed",
  case_assigned: "Case assigned",
  case_decision_set: "Decision set",
  case_reopened: "Case reopened",
  case_archived: "Case archived",

  // Documents
  document_uploaded: "Document uploaded",
  document_deleted: "Document deleted",
  document_reprocessed: "Document reprocessed",

  // Forensic checks
  forensic_check_started: "Forensic check started",
  forensic_check_completed: "Forensic check completed",
  ela_check_completed: "ELA check completed",
  copy_move_check_completed: "Copy-move check completed",
  ai_visual_check_completed: "AI visual check completed",
  metadata_check_completed: "Metadata check completed",
  font_consistency_check_completed: "Font consistency check completed",
  font_consistency_failed: "Font consistency check failed",
  cross_document_check_completed: "Cross-document check completed",

  // Signature references
  signature_reference_created: "Signature reference created",
  signature_reference_deleted: "Signature reference deleted",
  signature_match_completed: "Signature comparison completed",

  // Users / settings
  user_login: "User signed in",
  user_logout: "User signed out",
  user_created: "User created",
  user_updated: "User updated",
  user_password_changed: "Password changed",
  user_deactivated: "User deactivated",

  // Bulk uploads
  bulk_upload_created: "Bulk upload created",
  bulk_upload_completed: "Bulk upload completed",
  bulk_upload_failed: "Bulk upload failed",
}

/**
 * Returns a human-readable label for a given audit event_type.
 * Falls back to the raw event_type string if no label is defined.
 */
export function auditLabel(eventType: string): string {
  return AUDIT_EVENT_LABELS[eventType] ?? eventType
}

/** Maps audit event types to a visual tone for colour-coding. */
export function auditTone(eventType: string): AuditTone {
  if (
    eventType.includes("failed") ||
    eventType.includes("deleted") ||
    eventType.includes("deactivated")
  ) {
    return "rose"
  }
  if (
    eventType.includes("completed") ||
    eventType.includes("created") ||
    eventType === "user_login"
  ) {
    return "emerald"
  }
  if (eventType.includes("changed") || eventType.includes("updated")) {
    return "amber"
  }
  if (
    eventType.includes("completed") ||
    eventType.includes("created") ||
    eventType === "user_login"
  ) {
    return "emerald"
  }
  return "slate"
}

/**
 * Returns a short human-readable description for an audit event,
 * incorporating relevant fields from event_data when available.
 */
export function describeAuditEvent(
  eventType: string,
  eventData?: Record<string, unknown> | null
): string {
  const label = auditLabel(eventType)
  if (!eventData) return label

  // Enrich with the most useful context fields
  const parts: string[] = [label]

  if (typeof eventData.document_name === "string") {
    parts.push(`— ${eventData.document_name}`)
  } else if (typeof eventData.filename === "string") {
    parts.push(`— ${eventData.filename}`)
  }

  if (typeof eventData.status === "string") {
    parts.push(`(${eventData.status})`)
  }

  return parts.join(" ")
}
