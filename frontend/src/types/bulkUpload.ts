import type { CaseFlag, CaseStatus, CaseType, UserSummary } from "@/types/case"

// Mirrors backend/app/schemas/bulk_upload.py.

export type BulkUploadStatus = "queued" | "ingesting" | "complete" | "failed"

export const BULK_STATUS_LABELS: Record<BulkUploadStatus, string> = {
  queued: "Received",
  ingesting: "Creating cases",
  complete: "All cases handled",
  failed: "Zip failed",
}

/** Derived on every read from the case and its documents (never stored). */
export type BulkCaseLiveStatus = "validating" | "failed" | "queued" | "processing" | "done" | "flagged"

export interface BulkUploadFile {
  name: string
  /** skipped: its folder was rejected as a whole, so the file was never examined. */
  status: "pending" | "accepted" | "rejected" | "skipped"
  code: string | null
  message: string | null
  size_bytes: number | null
  document_id: string | null
}

export interface BulkUploadCase {
  index: number
  folder: string
  status: "pending" | "created" | "failed"
  error_code: string | null
  error_message: string | null
  case_id: string | null
  case_number: string | null
  files: BulkUploadFile[]
  live_status: BulkCaseLiveStatus
  case_status: CaseStatus | null
  documents_total: number
  documents_finished: number
  flag: CaseFlag | null
}

export type VerificationMode = "cross_document" | "document_forensics" | "both"

export const VERIFICATION_MODE_LABELS: Record<VerificationMode, { title: string; subtitle: string; short: string }> = {
  cross_document: {
    title: "Cross-Document Contradiction Detector",
    subtitle: "Compare person documents (Aadhaar, PAN, Voter, Income, etc.) to detect name variants, DoB conflicts, address differences, and transliterations.",
    short: "Cross-document",
  },
  document_forensics: {
    title: "Document Forensics & Authenticity",
    subtitle: "Examine individual ID documents for tampering, metadata forgery, font inconsistency, and digital alterations.",
    short: "Document forensics",
  },
  both: {
    title: "Both (Full 360° Inspection)",
    subtitle: "Comprehensive analysis: deep forensic tampering checks on each document AND cross-document contradiction detection.",
    short: "Full 360° check",
  },
}

export interface BulkUploadSummary {
  id: string
  original_filename: string
  case_type: CaseType
  status: BulkUploadStatus
  error_code: string | null
  error_message: string | null
  zip_size_bytes: number
  case_folder_count: number | null
  cases_created: number
  cases_failed: number
  documents_accepted: number
  documents_rejected: number
  uploaded_by: UserSummary | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  verification_mode?: VerificationMode | string | null
}

export type BulkUploadProgress = Record<BulkCaseLiveStatus, number>

export interface BulkUploadDetail extends BulkUploadSummary {
  wrapper_folder: string | null
  ignored_entries: string[]
  ignored_entry_count: number
  warnings: string[]
  progress: BulkUploadProgress
  /** Nothing on the screen can change any more; stop polling. */
  settled: boolean
  cases: BulkUploadCase[]
  verification_mode?: VerificationMode | string | null
}
