import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Building2Icon, GlobeIcon } from "lucide-react"

import { getOrganisation, type OrganisationInfo } from "@/api/organisation"
import { ApiError } from "@/api/client"
import { getOrgSubdomain, orgUrl } from "@/lib/organisation"

interface OrganisationContextValue {
  organisation: OrganisationInfo | null
  isLoading: boolean
  isOrgSite: boolean
  subdomain: string | null
}

const OrganisationContext = React.createContext<OrganisationContextValue | null>(null)

export function OrganisationProvider({ children }: { children: React.ReactNode }) {
  const currentSubdomain = getOrgSubdomain()

  const {
    data: organisation,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["organisation", currentSubdomain],
    queryFn: () => getOrganisation(currentSubdomain),
    staleTime: 60 * 60 * 1000,
    retry: false,
  })

  const is404 = error instanceof ApiError && error.status === 404

  if (is404) {
    const platformLink = orgUrl(null, "/")
    return (
      <div className="flex min-h-svh flex-col items-center justify-center bg-background px-4 py-12 text-center antialiased">
        <div className="max-w-md w-full rounded-3xl border border-border bg-card p-8 sm:p-10 shadow-lg flex flex-col items-center gap-5">
          <div className="p-4 rounded-2xl bg-muted text-muted-foreground">
            <Building2Icon className="size-10" />
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              This address is not in use
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              No organisation uses this address. Check the link you were given.
            </p>
          </div>
          <div className="pt-2">
            <a
              href={platformLink}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition shadow-xs"
            >
              <GlobeIcon className="size-3.5" />
              <span>Go to platform homepage</span>
            </a>
          </div>
        </div>
      </div>
    )
  }

  const value: OrganisationContextValue = {
    organisation: organisation ?? null,
    isLoading,
    isOrgSite: Boolean(currentSubdomain && organisation?.subdomain),
    subdomain: currentSubdomain,
  }

  return (
    <OrganisationContext.Provider value={value}>
      {children}
    </OrganisationContext.Provider>
  )
}

export function useOrganisation() {
  const ctx = React.useContext(OrganisationContext)
  if (!ctx) {
    throw new Error("useOrganisation must be used within an OrganisationProvider")
  }
  return ctx
}
