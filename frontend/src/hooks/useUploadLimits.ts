import { useQuery } from "@tanstack/react-query"

import { apiFetch } from "@/api/client"
import { useAuth } from "@/hooks/useAuth"

export interface UploadLimits {
  max_file_size_mb: number
  max_zip_size_mb: number
  max_file_size_bytes: number
  max_zip_size_bytes: number
}

export interface RetentionPolicy {
  /** Days an uploaded file is kept before it is removed; 0: kept. */
  document_retention_days: number
  /** Whether a private upload (removed at sign-out) can be offered. */
  private_upload_available: boolean
}

/** How long the signed-in user's uploads are kept. Null while loading. */
export function useRetentionPolicy(): RetentionPolicy | null {
  const { token, user } = useAuth()
  const { data } = useQuery({
    queryKey: ["retention-policy", token],
    queryFn: () => apiFetch<RetentionPolicy>("/auth/me/retention", { token }),
    enabled: Boolean(token) && Boolean(user),
    staleTime: 5 * 60 * 1000,
  })
  return data ?? null
}

/**
 * The signed-in user's company upload limits (per company, set by a platform
 * admin). Re-read whenever an upload screen mounts, so a limit changed
 * mid-session shows up without signing in again. Null while loading, and for
 * platform admins, who have no company.
 */
export function useUploadLimits(): UploadLimits | null {
  const { token, user } = useAuth()
  const { data } = useQuery({
    queryKey: ["upload-limits", token],
    queryFn: () => apiFetch<UploadLimits>("/auth/me/upload-limits", { token }),
    enabled: Boolean(token) && Boolean(user) && !user?.is_platform_admin,
    staleTime: 0,
    refetchOnMount: "always",
  })
  return data ?? null
}
