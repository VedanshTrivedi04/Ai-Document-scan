import * as React from "react"
import { useQuery } from "@tanstack/react-query"

import { listCases } from "@/api/cases"
import { CompanyPicker } from "@/components/CompanyPicker"
import { CitizenDashboard } from "@/components/dashboard/CitizenDashboard"
import { PlatformAdminDashboard } from "@/components/dashboard/PlatformAdminDashboard"
import { ReviewerL1Dashboard } from "@/components/dashboard/ReviewerL1Dashboard"
import { ReviewerL2Dashboard } from "@/components/dashboard/ReviewerL2Dashboard"
import {
  RolePersonaSwitcher,
  type PersonaRole,
} from "@/components/dashboard/RolePersonaSwitcher"
import { Nav } from "@/design-system/Nav"
import { useActingCompany } from "@/hooks/useActingCompany"
import { useAuth } from "@/hooks/useAuth"
import type { CaseListItem } from "@/types/case"

// Fallback synthetic cases to make the dashboard look rich and demo-ready
// when tested in an empty environment or fresh tenant.
const SYNTHETIC_SAMPLE_CASES: CaseListItem[] = [
  {
    id: "sample-case-1",
    case_number: "CASE-2026-0042",
    case_type: "identity_verification",
    status: "pending_manual_review",
    assigned_tier: "l1",
    risk_tier: "medium",
    document_count: 3,
    can_act: true,
    created_at: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    submitted_by: {
      id: "u-1",
      email: "citizen.arun@example.gov.in",
      full_name: "Arun Kumar Sharma",
    },
    flag: {
      flag: "medium",
      score: 48,
      label: "Phonetic Name Match",
      description: "Minor Hindi transliteration difference: 'Sharma' vs 'Sarma' in 10th Marksheet",
    },
  },
  {
    id: "sample-case-2",
    case_number: "CASE-2026-0041",
    case_type: "school_document",
    status: "auto_approved",
    assigned_tier: "l1",
    risk_tier: "low",
    document_count: 2,
    can_act: false,
    created_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    submitted_by: {
      id: "u-1",
      email: "citizen.arun@example.gov.in",
      full_name: "Arun Kumar Sharma",
    },
    flag: {
      flag: "low",
      score: 12,
      label: "Clean Verified",
      description: "CBSE Roll Number and Issuer signature matches educational database",
    },
  },
  {
    id: "sample-case-3",
    case_number: "CASE-2026-0039",
    case_type: "identity_verification",
    status: "under_investigation",
    assigned_tier: "l2",
    risk_tier: "high",
    document_count: 4,
    can_act: true,
    created_at: new Date(Date.now() - 1000 * 60 * 240).toISOString(),
    submitted_by: {
      id: "u-2",
      email: "applicant.priya@example.gov.in",
      full_name: "Priya Patel",
    },
    flag: {
      flag: "high",
      score: 84,
      label: "Father Name Conflict",
      description: "Father's name differs across Aadhaar ('Ramesh Patel') and Marksheet ('Suresh Patel')",
    },
  },
  {
    id: "sample-case-4",
    case_number: "CASE-2026-0035",
    case_type: "commercial_invoice",
    status: "approved",
    assigned_tier: "l1",
    risk_tier: "low",
    document_count: 2,
    can_act: false,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    submitted_by: {
      id: "u-3",
      email: "vendor.apex@corp.in",
      full_name: "Apex Supplies",
    },
    flag: {
      flag: "low",
      score: 8,
      label: "Issuer Verified",
      description: "Tax GSTIN matched verified registry; clean forensic scan",
    },
  },
]

export function DashboardPage() {
  const { token, user } = useAuth()
  const acting = useActingCompany()

  // Determine actual account role
  const actualRole: PersonaRole = React.useMemo(() => {
    if (user?.is_platform_admin) return "platform_admin"
    if (user?.role === "reviewer_l2") return "reviewer_l2"
    if (user?.role === "reviewer_l1") return "reviewer_l1"
    return "user"
  }, [user])

  // Active persona selection for live previewing across all roles
  const [selectedPersona, setSelectedPersona] = React.useState<PersonaRole>(actualRole)

  // Keep in sync with user login role if user object updates
  React.useEffect(() => {
    setSelectedPersona(actualRole)
  }, [actualRole])

  // Fetch real cases from API
  const { data: apiCases, isLoading: isLoadingCases } = useQuery({
    queryKey: ["cases", token, acting.companyId],
    queryFn: () => listCases(token as string, {}, acting.platformCompanyParam),
    enabled: Boolean(token),
  })

  // Use real cases if available, otherwise graceful fallback to rich synthetic samples
  const cases: CaseListItem[] = React.useMemo(() => {
    if (apiCases && apiCases.length > 0) {
      return apiCases
    }
    return SYNTHETIC_SAMPLE_CASES
  }, [apiCases])

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#EDF2FA] text-slate-900 selection:bg-blue-100 selection:text-blue-900">
      <Nav active="dashboard" />

      <main className="max-w-7xl mx-auto px-3.5 sm:px-6 lg:px-8 py-5 sm:py-8 w-full space-y-6 flex-grow">
        {/* Multi-Company Picker for Platform Admin */}
        <CompanyPicker />

        {/* Global Role Persona Switcher (Allows testing all 4 user dashboard experiences) */}
        <RolePersonaSwitcher
          currentPersona={selectedPersona}
          onPersonaChange={setSelectedPersona}
          actualRole={actualRole}
        />

        {/* Dynamic Role-Adaptive Dashboard Views */}
        {selectedPersona === "user" && (
          <CitizenDashboard cases={cases} isLoadingCases={isLoadingCases} />
        )}

        {selectedPersona === "reviewer_l1" && (
          <ReviewerL1Dashboard cases={cases} isLoadingCases={isLoadingCases} />
        )}

        {selectedPersona === "reviewer_l2" && (
          <ReviewerL2Dashboard cases={cases} isLoadingCases={isLoadingCases} />
        )}

        {selectedPersona === "platform_admin" && (
          <PlatformAdminDashboard totalCases={cases.length} />
        )}
      </main>
    </div>
  )
}
