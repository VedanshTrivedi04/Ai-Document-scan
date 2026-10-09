/**
 * Upload limit constants and client-side validation helpers.
 *
 * Single source of truth for file-size caps, accepted MIME types,
 * and bulk-upload thresholds — used across FileDropzone, NewCasePage,
 * BulkUploadPage, BulkUploadDetailPage, and BulkUploadsListPage.
 *
 * Keep in sync with backend/app/config.py and backend/app/api/cases.py.
 */

// ---------------------------------------------------------------------------
// Size constants
// ---------------------------------------------------------------------------

/** Maximum size (bytes) for a single document upload — 50 MB. */
export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

/** Maximum size (bytes) for a bulk ZIP upload — 500 MB. */
export const MAX_ZIP_SIZE_BYTES = 500 * 1024 * 1024

/** Maximum number of individual files allowed in one case upload. */
export const MAX_FILES_PER_CASE = 20

/** Maximum number of cases estimated in a bulk ZIP before we warn. */
export const BULK_CASE_WARNING_THRESHOLD = 500

// ---------------------------------------------------------------------------
// Accepted MIME types
// ---------------------------------------------------------------------------

/** MIME types accepted for standard document uploads. */
export const ACCEPTED_UPLOAD_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/tiff": [".tif", ".tiff"],
  "image/webp": [".webp"],
}

/** MIME types accepted for identity document uploads (stricter set). */
export const ACCEPTED_IDENTITY_UPLOAD_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
}

/**
 * Flat comma-separated string for <input accept="..."> — standard uploads.
 * e.g. ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp"
 */
export const ACCEPTED_UPLOAD_TYPES_STRING = Object.values(ACCEPTED_UPLOAD_TYPES)
  .flat()
  .join(",")

/**
 * Flat comma-separated string for <input accept="..."> — identity uploads.
 */
export const ACCEPTED_IDENTITY_UPLOAD_TYPES_STRING = Object.values(
  ACCEPTED_IDENTITY_UPLOAD_TYPES
)
  .flat()
  .join(",")

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Human-readable file size string.
 * e.g. formatFileSize(1536) → "1.5 KB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)
  return `${value % 1 === 0 ? value : value.toFixed(1)} ${units[i]}`
}

interface UploadProblemOptions {
  /** If true, images (JPG, PNG, TIFF, WebP) are accepted in addition to PDF. */
  allowImages?: boolean
}

/**
 * Returns a user-facing error string if the file fails client-side
 * validation, or null if it's OK.
 *
 * @param file       - The file to validate.
 * @param maxFileBytes - The per-file size limit from the server (null = use default).
 * @param options    - Additional options (e.g. allowImages).
 */
export function clientUploadProblem(
  file: File,
  maxFileBytes?: number | null,
  options?: UploadProblemOptions
): string | null {
  const allowImages = options?.allowImages ?? true
  const types = allowImages ? ACCEPTED_UPLOAD_TYPES : { "application/pdf": [".pdf"] }
  const accepted = Object.values(types).flat()
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`
  if (!accepted.includes(ext)) {
    return `Unsupported file type "${ext}". ${
      allowImages
        ? "Please upload PDF, JPG, PNG, TIFF, or WebP."
        : "Please upload PDF only."
    }`
  }
  const limit = maxFileBytes ?? MAX_FILE_SIZE_BYTES
  if (file.size > limit) {
    return `File is too large (${formatFileSize(file.size)}). Maximum allowed size is ${formatFileSize(limit)}.`
  }
  return null
}

/**
 * Returns a user-facing error string if the ZIP fails client-side
 * validation for a bulk upload, or null if it's OK.
 *
 * @param file       - The ZIP file to validate.
 * @param maxZipBytes - The ZIP size limit from the server (null = use default).
 */
export function clientZipProblem(
  file: File,
  maxZipBytes?: number | null
): string | null {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`
  if (ext !== ".zip") {
    return `Only ZIP files are accepted for bulk upload. Got "${ext}".`
  }
  const limit = maxZipBytes ?? MAX_ZIP_SIZE_BYTES
  if (file.size > limit) {
    return `ZIP is too large (${formatFileSize(file.size)}). Maximum allowed size is ${formatFileSize(limit)}.`
  }
  return null
}

/**
 * Estimates the number of cases in a ZIP file based on its size.
 * Uses file.size directly — no async read needed.
 *
 * @param file - The ZIP File object.
 */
export async function estimateZipCaseCount(file: File): Promise<number> {
  const avgCaseSizeBytes = 3 * 2 * 1024 * 1024 // 3 docs × 2 MB each
  return Math.max(1, Math.round(file.size / avgCaseSizeBytes))
}
