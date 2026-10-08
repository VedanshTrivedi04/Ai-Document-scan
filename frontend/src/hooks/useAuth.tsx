import * as React from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { getMe, login as loginRequest, register as registerRequest, type LoginPayload, type RegisterPayload } from "@/api/auth"
import type { CurrentUser, TokenResponse } from "@/types/auth"

const TOKEN_STORAGE_KEY = "docauth.token"

interface AuthContextValue {
  token: string | null
  user: CurrentUser | undefined
  isLoadingUser: boolean
  login: (payload: LoginPayload) => Promise<TokenResponse>
  register: (payload: RegisterPayload) => Promise<TokenResponse>
  logout: () => void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = React.useState<string | null>(() =>
    localStorage.getItem(TOKEN_STORAGE_KEY)
  )

  const {
    data: user,
    isLoading: isLoadingUser,
    isError,
  } = useQuery({
    queryKey: ["me", token],
    queryFn: () => getMe(token as string),
    enabled: Boolean(token),
    retry: false,
  })

  // A stored token that the backend no longer accepts (expired/invalid) —
  // drop it so the app falls back to the login screen instead of hanging
  // on a permanently failed query.
  React.useEffect(() => {
    if (isError && token) {
      setToken(null)
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  }, [isError, token])

  // Listen for unauthorized 401s (e.g. from an API request to another org)
  React.useEffect(() => {
    const handleUnauthorized = () => {
      setToken(null)
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      queryClient.removeQueries({ queryKey: ["me"] })
    }
    window.addEventListener("auth:unauthorized", handleUnauthorized)
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized)
  }, [queryClient])

  const _storeToken = React.useCallback((resp: TokenResponse) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, resp.access_token)
    setToken(resp.access_token)
    return resp
  }, [])

  const login = React.useCallback(
    async (payload: LoginPayload): Promise<TokenResponse> => {
      const resp = await loginRequest(payload)
      return _storeToken(resp)
    },
    [_storeToken]
  )

  const register = React.useCallback(
    async (payload: RegisterPayload): Promise<TokenResponse> => {
      const resp = await registerRequest(payload)
      return _storeToken(resp)
    },
    [_storeToken]
  )

  const logout = React.useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setToken(null)
    queryClient.removeQueries({ queryKey: ["me"] })
  }, [queryClient])

  const value = React.useMemo(
    () => ({ token, user, isLoadingUser: Boolean(token) && isLoadingUser, login, register, logout }),
    [token, user, isLoadingUser, login, register, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return ctx
}
