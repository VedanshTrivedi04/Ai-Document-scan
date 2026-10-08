import { apiFetch } from "@/api/client"
import type { CurrentUser, TokenResponse } from "@/types/auth"

export interface LoginPayload {
  email: string
  password: string
}

export function login(payload: LoginPayload): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export interface RegisterPayload {
  full_name: string
  email: string
  password: string
}

// Public citizen self-registration — no token needed.
// On success returns a ready-to-use bearer token (user is logged in immediately).
export function register(payload: RegisterPayload): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
}

// Change your own password (every role). A forgotten password is reset by a
// platform admin instead (Settings → Users → Reset password).
export function changePassword(payload: ChangePasswordPayload, token: string): Promise<void> {
  return apiFetch<void>("/auth/me/password", { method: "POST", body: JSON.stringify(payload), token })
}

export function getMe(token: string): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me", { token })
}
