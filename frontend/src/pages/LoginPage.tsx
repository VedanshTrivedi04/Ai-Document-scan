import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import {
  ArrowRightIcon,
  Building2Icon,
  EyeIcon,
  EyeOffIcon,
  GlobeIcon,
  LockIcon,
  MailIcon,
  ShieldCheckIcon,
} from "lucide-react"
import { useForm } from "react-hook-form"
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { getLanguages } from "@/api/i18n"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/hooks/useAuth"
import { useOrganisation } from "@/hooks/useOrganisation"
import { APP_FULL_NAME, APP_NAME } from "@/lib/appInfo"
import { getBaseDomain, getOrgSubdomain, orgUrl } from "@/lib/organisation"

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const { token, login } = useAuth()
  const { organisation, isOrgSite } = useOrganisation()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get("email") || ""

  const [formError, setFormError] = React.useState<string | null>(null)
  const [showPassword, setShowPassword] = React.useState(false)

  // Redirection prompt when user logs in on platform site but belongs to an organisation
  const [redirectPrompt, setRedirectPrompt] = React.useState<{
    targetSubdomain: string
    targetUrl: string
    targetHost: string
  } | null>(null)

  // Language management
  const [currentLang, setCurrentLang] = React.useState<string>(() => {
    try {
      return localStorage.getItem("agnitia_lang") || "en"
    } catch {
      return "en"
    }
  })

  React.useEffect(() => {
    try {
      localStorage.setItem("agnitia_lang", currentLang)
    } catch {
      // ignore
    }
  }, [currentLang])

  const { data: languages = [] } = useQuery({
    queryKey: ["i18nLanguages"],
    queryFn: () => getLanguages(),
    staleTime: 5 * 60 * 1000,
  })
  const availableLanguages = React.useMemo(() => languages.filter((l) => l.available), [languages])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: initialEmail, password: "" },
  })

  // Already authenticated — don't show the login form again.
  if (token && !redirectPrompt) {
    const from = (location.state as { from?: string } | null)?.from ?? "/"
    return <Navigate to={from} replace />
  }

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null)
    setRedirectPrompt(null)
    try {
      const resp = await login(values)
      const currentSubdomain = getOrgSubdomain()

      // If the user's company has a subdomain that differs from current site
      if (resp.company_subdomain && resp.company_subdomain !== currentSubdomain) {
        const base = getBaseDomain()
        const targetHost = `${resp.company_subdomain}.${base}`
        const targetUrl = orgUrl(
          resp.company_subdomain,
          `/login?email=${encodeURIComponent(values.email)}`
        )
        setRedirectPrompt({
          targetSubdomain: resp.company_subdomain,
          targetUrl,
          targetHost,
        })
        return
      }

      navigate("/", { replace: true })
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again."
      )
    }
  }

  const baseDomain = getBaseDomain()
  const displayHost = organisation?.subdomain
    ? `${organisation.subdomain}.${organisation.base_domain || baseDomain}`
    : baseDomain

  return (
    <div className="flex min-h-svh flex-col justify-between bg-background p-4 sm:p-6 lg:p-8">
      <div aria-hidden className="hidden sm:block sm:h-4 lg:h-6" />

      <main className="mx-auto w-full max-w-[460px]">
        <div className="rounded-3xl border border-accent/15 bg-card p-5 sm:p-8 md:p-10 shadow-card">
          <header className="mb-6 sm:mb-8 text-center">
            <div className="mb-4 sm:mb-5 flex items-center justify-center gap-3">
              <img src="/logo.png" alt="" className="size-9 sm:size-10 rounded-xl shadow-sm shadow-accent/20" />
              <div className="text-left">
                <span className="block text-lg sm:text-xl font-bold leading-tight tracking-tight text-foreground">
                  {APP_NAME}
                </span>
                <span className="block text-[9px] sm:text-[9.5px] font-bold uppercase tracking-widest text-muted-foreground">
                  {APP_FULL_NAME}
                </span>
              </div>
            </div>

            {isOrgSite && organisation?.name ? (
              <div>
                <p className="mb-1 text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Sign in to
                </p>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                  {organisation.name}
                </h1>
                <p className="mt-1 text-xs text-muted-foreground font-mono">
                  {displayHost}
                </p>
              </div>
            ) : (
              <div>
                <p className="mb-2 text-[10px] sm:text-[11px] font-bold uppercase tracking-widest text-accent">
                  Secure access portal
                </p>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                  Sign in to your account
                </h1>
                <p className="mt-1.5 text-xs sm:text-sm leading-relaxed text-muted-foreground">
                  Review submitted claims and their document authenticity checks.
                </p>
              </div>
            )}
          </header>

          {redirectPrompt ? (
            <div className="flex flex-col gap-4 text-center py-2 animate-in fade-in duration-200">
              <div className="size-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto mb-1">
                <Building2Icon className="size-6" />
              </div>
              <div className="flex flex-col gap-1.5">
                <h2 className="text-lg font-bold text-foreground">
                  Your organisation's site is{" "}
                  <span className="font-mono text-primary">{redirectPrompt.targetHost}</span>
                </h2>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Continue there to access your organisation's verification workspace.
                </p>
              </div>

              <div className="pt-2">
                <a
                  href={redirectPrompt.targetUrl}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition shadow-sm"
                >
                  <span>Continue to {redirectPrompt.targetHost}</span>
                  <ArrowRightIcon className="size-3.5" />
                </a>
              </div>
            </div>
          ) : (
            <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
              <div>
                <Label htmlFor="email" className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-foreground">
                  Work email
                </Label>
                <div className="relative">
                  <MailIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    aria-invalid={Boolean(errors.email)}
                    className="h-11 rounded-xl border-border bg-secondary/40 pl-10 focus-visible:bg-card"
                    {...register("email")}
                  />
                </div>
                {errors.email && <p className="mt-1.5 text-sm text-destructive">{errors.email.message}</p>}
              </div>

              <div>
                <Label htmlFor="password" className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-foreground">
                  Password
                </Label>
                <div className="relative">
                  <LockIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    aria-invalid={Boolean(errors.password)}
                    className="h-11 rounded-xl border-border bg-secondary/40 pl-10 pr-10 focus-visible:bg-card"
                    {...register("password")}
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                  </button>
                </div>
                {errors.password && <p className="mt-1.5 text-sm text-destructive">{errors.password.message}</p>}
              </div>

              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  id="trustDevice"
                  defaultChecked
                  className="mt-0.5 size-4 rounded border-border text-accent focus:ring-accent"
                />
                <div>
                  <label htmlFor="trustDevice" className="text-sm font-medium text-foreground cursor-pointer">
                    Trust this device for 30 days
                  </label>
                  <p className="text-xs text-muted-foreground">Enforces hardware cryptographic binding</p>
                </div>
              </div>

              {formError && (
                <p role="alert" className="text-sm text-destructive">
                  {formError}
                </p>
              )}

              <Button
                type="submit"
                disabled={isSubmitting}
                className="mt-2 h-11 w-full rounded-xl bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
              >
                {isSubmitting
                  ? "Signing in…"
                  : isOrgSite && organisation?.name
                  ? `Sign in to ${organisation.name}`
                  : `Sign in to ${APP_NAME}`}
                {!isSubmitting && <ArrowRightIcon className="size-4" />}
              </Button>

              <div className="relative flex items-center justify-center py-2">
                <div className="absolute inset-x-0 top-1/2 h-px bg-border" />
                <span className="relative bg-card px-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  Or Corporate SSO
                </span>
              </div>
              <button
                type="button"
                disabled
                className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-border bg-card text-sm font-medium text-foreground transition hover:bg-secondary/60 disabled:opacity-70"
              >
                <ShieldCheckIcon className="size-4 text-accent" />
                Sign in with SAML / Okta SSO
              </button>

              {/* Language: globe switcher (Phase 4) */}
              {availableLanguages.length > 0 && (
                <div className="mt-2 pt-3 border-t border-border/60 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                  <GlobeIcon className="size-3.5 text-muted-foreground shrink-0" />
                  <span className="text-[11px] font-medium">Language:</span>
                  <select
                    value={currentLang}
                    onChange={(e) => setCurrentLang(e.target.value)}
                    className="bg-transparent border-none text-xs font-semibold text-foreground focus:outline-hidden cursor-pointer"
                    aria-label="Interface language"
                  >
                    {availableLanguages.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.native_name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </form>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <ShieldCheckIcon className="size-3.5 text-accent" />
            SOC 2 Type II Certified
          </span>
          <span>·</span>
          <span>256-bit TLS Encryption</span>
          <span>·</span>
          <span>Zero-knowledge logs</span>
        </div>
      </main>

      <footer className="flex flex-wrap items-center justify-center gap-4 pb-3 pt-8 text-xs text-muted-foreground">
        <span className="cursor-pointer hover:text-foreground">Terms of Service</span>
        <span className="cursor-pointer hover:text-foreground">Privacy Policy</span>
        <span className="cursor-pointer hover:text-foreground">Forensic Architecture Whitepaper</span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-success" />
          Systems Operational
        </span>
      </footer>
      <p className="pb-2 text-center text-[11px] text-muted-foreground">
        © {new Date().getFullYear()} {APP_NAME} — {APP_FULL_NAME}. All rights reserved.
      </p>
    </div>
  )
}
