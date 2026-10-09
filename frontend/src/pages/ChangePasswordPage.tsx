import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EyeIcon, EyeOffIcon, KeyRoundIcon, Loader2Icon } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { changePassword } from "@/api/auth"
import { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import { FieldError, invalidFieldClass, visibleError } from "@/components/ui/field-error"
import { useAuth } from "@/hooks/useAuth"

const MIN_PASSWORD = 8
const MAX_PASSWORD = 128
const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 pr-9 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"

/**
 * Shown to a person who signed in with a temporary password (set by their
 * family head). Everything else is blocked until they choose their own
 * (see ProtectedRoute).
 */
export function ChangePasswordPage() {
  const { token, user, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [current, setCurrent] = React.useState("")
  const [next, setNext] = React.useState("")
  const [confirm, setConfirm] = React.useState("")
  const [show, setShow] = React.useState(false)
  const [touched, setTouched] = React.useState<Record<string, boolean>>({})
  const [submitted, setSubmitted] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const touch = (field: string) => () => setTouched((t) => ({ ...t, [field]: true }))

  const currentError = current ? null : "Enter the temporary password you were given."
  const nextError =
    next.length < MIN_PASSWORD
      ? `Use at least ${MIN_PASSWORD} characters.`
      : next.length > MAX_PASSWORD
        ? `Use at most ${MAX_PASSWORD} characters.`
        : next === current
          ? "Your new password must be different from the temporary one."
          : null
  const confirmError = confirm === next ? null : "The two passwords do not match."
  const errors = { "current-password": currentError, "new-password": nextError, "confirm-password": confirmError }
  const shown = (field: keyof typeof errors) => visibleError(errors, field, touched, submitted)

  const change = useMutation({
    mutationFn: () => changePassword({ current_password: current, new_password: next }, token as string),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] })
      navigate(user?.role === "user" ? "/family" : "/cases", { replace: true })
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not change the password."),
  })

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitted(true)
    setError(null)
    if (currentError || nextError || confirmError) return
    change.mutate()
  }

  return (
    <div className="min-h-svh flex items-center justify-center bg-[#F1F5FA] px-4 py-10 font-sans text-slate-900">
      <form
        onSubmit={submit}
        noValidate
        className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl flex flex-col gap-4"
      >
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-full bg-blue-100 text-blue-700">
            <KeyRoundIcon className="size-5" />
          </div>
          <div>
            <h1 className="text-lg font-extrabold tracking-tight">Choose your own password</h1>
            <p className="text-xs text-muted-foreground">
              {user?.full_name ? `${user.full_name}, y` : "Y"}ou signed in with a temporary password. Pick one only you
              know before you continue.
            </p>
          </div>
        </div>

        {error && (
          <div role="alert" className="p-2.5 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3.5 text-xs">
          <div className="flex flex-col gap-1">
            <label htmlFor="current-password" className="font-semibold">
              Temporary password
            </label>
            <div className="relative">
              <input
                id="current-password"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                onBlur={touch("current-password")}
                className={`${inputClass} ${shown("current-password") ? invalidFieldClass : ""}`}
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                aria-label={show ? "Hide passwords" : "Show passwords"}
              >
                {show ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
              </button>
            </div>
            <FieldError id="current-password-error" message={shown("current-password")} />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="new-password" className="font-semibold">
              New password
            </label>
            <input
              id="new-password"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              onBlur={touch("new-password")}
              className={`${inputClass} ${shown("new-password") ? invalidFieldClass : ""}`}
            />
            <FieldError id="new-password-error" message={shown("new-password")} />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="confirm-password" className="font-semibold">
              Confirm new password
            </label>
            <input
              id="confirm-password"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              onBlur={touch("confirm-password")}
              className={`${inputClass} ${shown("confirm-password") ? invalidFieldClass : ""}`}
            />
            <FieldError id="confirm-password-error" message={shown("confirm-password")} />
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 pt-3 border-t border-border/80">
          <Button type="button" variant="ghost" size="sm" onClick={logout} className="text-xs">
            Sign out
          </Button>
          <Button type="submit" size="sm" disabled={change.isPending} className="text-xs font-semibold gap-1.5">
            {change.isPending && <Loader2Icon className="size-3.5 animate-spin" />}
            <span>Save password</span>
          </Button>
        </div>
      </form>
    </div>
  )
}
