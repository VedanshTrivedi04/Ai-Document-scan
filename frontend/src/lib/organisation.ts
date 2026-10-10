/**
 * Organisation / subdomain routing helpers.
 *
 * The platform runs at a root domain (e.g. docsure.com) and each
 * organisation has its own subdomain (e.g. acme.docsure.com).
 * These utilities help detect and construct those URLs.
 */

const ORG_SUBDOMAIN_KEY = "VITE_ORG_SUBDOMAIN"

/**
 * Returns the current organisation subdomain, or null when on the
 * platform root site.
 *
 * In local development the subdomain is read from the env var
 * VITE_ORG_SUBDOMAIN so you can test org-scoped behaviour without DNS.
 * In production it's derived from the first hostname label if it isn't
 * "www" or matches the root domain.
 */
export function getOrgSubdomain(): string | null {
  // Allow overriding via env for local dev / Docker
  const envOverride = import.meta.env[ORG_SUBDOMAIN_KEY]
  if (envOverride) return envOverride as string

  const hostname = window.location.hostname
  const parts = hostname.split(".")

  // Platform hosting domains (e.g., myservice.onrender.com, myapp.vercel.app)
  // These 3-part hostnames represent the root platform service, NOT an organisation subdomain!
  const isPlatformHosting =
    hostname.endsWith(".onrender.com") ||
    hostname.endsWith(".vercel.app") ||
    hostname.endsWith(".netlify.app")

  if (isPlatformHosting) {
    if (parts.length >= 4) {
      return parts[0]
    }
    return null
  }

  // e.g. acme.docsure.com → ["acme", "docsure", "com"] → "acme"
  // e.g. docsure.com or localhost → no subdomain
  if (parts.length >= 3 && parts[0] !== "www") {
    return parts[0]
  }
  return null
}

/**
 * Returns the base domain (without any subdomain prefix).
 * e.g. "acme.docsure.com" → "docsure.com"
 *      "docsure.com"       → "docsure.com"
 *      "localhost"         → "localhost"
 */
export function getBaseDomain(): string {
  const hostname = window.location.hostname
  const parts = hostname.split(".")

  const isPlatformHosting =
    hostname.endsWith(".onrender.com") ||
    hostname.endsWith(".vercel.app") ||
    hostname.endsWith(".netlify.app")

  if (isPlatformHosting) {
    if (parts.length >= 4) {
      return parts.slice(1).join(".")
    }
    return hostname
  }

  if (parts.length >= 3 && parts[0] !== "www") {
    return parts.slice(1).join(".")
  }
  return hostname
}


/**
 * Builds a full URL for a given organisation subdomain and path.
 * Pass null as subdomain to build a URL for the platform root site.
 */
export function orgUrl(subdomain: string | null, path: string): string {
  const base = getBaseDomain()
  const protocol = window.location.protocol
  const port = window.location.port ? `:${window.location.port}` : ""
  const host = subdomain ? `${subdomain}.${base}` : base
  return `${protocol}//${host}${port}${path}`
}

/**
 * Validates an organisation subdomain string.
 * Rules (mirrors backend validation):
 *  - 3–63 characters
 *  - Lowercase letters, digits, and hyphens only
 *  - Must start and end with a letter or digit (no leading/trailing hyphens)
 *
 * @returns An error message string if invalid, or null if valid.
 */
export function validateSubdomain(value: string): string | null {
  if (!value) return "Subdomain is required."
  if (value.length < 3) return "Subdomain must be at least 3 characters."
  if (value.length > 63) return "Subdomain must be 63 characters or fewer."
  if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(value)) {
    return "Subdomain may only contain lowercase letters, numbers, and hyphens, and must not start or end with a hyphen."
  }
  return null
}
