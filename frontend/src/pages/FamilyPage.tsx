import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  GlobeIcon,
  HomeIcon,
  Loader2Icon,
  UserPlusIcon,
  UsersIcon,
} from "lucide-react"
import { useParams } from "react-router-dom"

import { getLanguages } from "@/api/i18n"
import {
  addFamilyMember,
  createFamily,
  getFamilyById,
  getMyFamily,
  removeFamilyMember,
  updateFamilyMember,
} from "@/api/family"
import { AddMemberModal } from "@/components/family/AddMemberModal"
import { CreateFamilyCard } from "@/components/family/CreateFamilyCard"
import { EditMemberModal } from "@/components/family/EditMemberModal"
import { FamilyChecksPanel } from "@/components/family/FamilyChecksPanel"
import { FamilyMembersList } from "@/components/family/FamilyMembersList"
import { Button } from "@/components/ui/button"
import { Nav } from "@/design-system/Nav"
import { useAuth } from "@/hooks/useAuth"
import type {
  FamilyCreatePayload,
  FamilyMember,
  MemberCreatePayload,
  MemberUpdatePayload,
} from "@/types/family"

const PAGE_I18N: Record<string, Record<string, string>> = {
  en: {
    eyebrow: "Household Identity",
    add_member: "Add member",
    loading_family: "Loading family details…",
    family_not_found: "Family not found or access denied.",
    reviewer_banner: "Reviewer view — read-only household verification context.",
    members_count: "members",
  },
  hi: {
    eyebrow: "पारिवारिक पहचान",
    add_member: "सदस्य जोड़ें",
    loading_family: "परिवार का विवरण लोड हो रहा है…",
    family_not_found: "परिवार नहीं मिला या पहुंच अस्वीकृत है।",
    reviewer_banner: "समीक्षक दृश्य — केवल पढ़ने योग्य पारिवारिक सत्यापन संदर्भ।",
    members_count: "सदस्य",
  },
}

export function FamilyPage() {
  const { familyId } = useParams<{ familyId?: string }>()
  const { token, user } = useAuth()
  const queryClient = useQueryClient()

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

  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = PAGE_I18N[langKey] ?? PAGE_I18N.en

  // Available languages
  const { data: languages = [] } = useQuery({
    queryKey: ["i18nLanguages"],
    queryFn: () => getLanguages(),
    staleTime: 5 * 60 * 1000,
  })
  const availableLanguages = React.useMemo(() => languages.filter((l) => l.available), [languages])

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false)
  const [editingMember, setEditingMember] = React.useState<FamilyMember | null>(null)
  const [removingMemberId, setRemovingMemberId] = React.useState<string | null>(null)

  // Fetch Family View
  const isSpecificFamily = Boolean(familyId)
  const isPlatformAdmin = Boolean(user?.is_platform_admin)

  const {
    data: familyData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["family", isSpecificFamily ? familyId : "mine", currentLang, token],
    queryFn: () => {
      if (!token) return Promise.resolve(null)
      if (familyId) {
        return getFamilyById(familyId, currentLang, token)
      }
      return getMyFamily(currentLang, token)
    },
    enabled: Boolean(token && (!isPlatformAdmin || isSpecificFamily)),
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (payload: FamilyCreatePayload) => {
      if (!token) throw new Error("Missing auth token")
      return createFamily(payload, currentLang, token)
    },
    onSuccess: (newFamily) => {
      queryClient.setQueryData(["family", "mine", currentLang, token], newFamily)
      queryClient.invalidateQueries({ queryKey: ["family"] })
    },
  })

  const addMemberMutation = useMutation({
    mutationFn: (payload: MemberCreatePayload) => {
      if (!token) throw new Error("Missing auth token")
      return addFamilyMember(payload, currentLang, token)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["family", isSpecificFamily ? familyId : "mine", currentLang, token], updated)
      queryClient.invalidateQueries({ queryKey: ["family"] })
    },
  })

  const updateMemberMutation = useMutation({
    mutationFn: ({ memberId, payload }: { memberId: string; payload: MemberUpdatePayload }) => {
      if (!token) throw new Error("Missing auth token")
      return updateFamilyMember(memberId, payload, currentLang, token)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["family", isSpecificFamily ? familyId : "mine", currentLang, token], updated)
      queryClient.invalidateQueries({ queryKey: ["family"] })
    },
  })

  const removeMemberMutation = useMutation({
    mutationFn: (memberId: string) => {
      if (!token) throw new Error("Missing auth token")
      setRemovingMemberId(memberId)
      return removeFamilyMember(memberId, currentLang, token)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["family", isSpecificFamily ? familyId : "mine", currentLang, token], updated)
      queryClient.invalidateQueries({ queryKey: ["family"] })
    },
    onSettled: () => {
      setRemovingMemberId(null)
    },
  })

  const isHead = Boolean(
    familyData && user && String(familyData.head_user_id) === String(user.id)
  )

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="family" />
        <main className="max-w-2xl w-full mx-auto px-6 py-20 text-center flex flex-col items-center justify-center gap-3">
          <Loader2Icon className="size-8 text-primary animate-spin" />
          <p className="text-sm text-slate-600 font-medium">{t.loading_family}</p>
        </main>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="family" />
        <main className="max-w-2xl w-full mx-auto px-6 py-16 text-center">
          <h1 className="text-lg font-bold text-slate-800">{t.family_not_found}</h1>
        </main>
      </div>
    )
  }

  if (isPlatformAdmin && !isSpecificFamily) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="family" />
        <main className="max-w-xl w-full mx-auto px-6 py-16 text-center flex flex-col items-center justify-center">
          <div className="p-3 rounded-full bg-blue-100 text-blue-700 mb-3">
            <UsersIcon className="size-6" />
          </div>
          <h1 className="text-lg font-bold text-slate-900">Platform Admin Account</h1>
          <p className="text-xs text-muted-foreground mt-2 max-w-sm">
            Platform administrators do not have a personal family view. To inspect a household, open a case or view a family using its ID.
          </p>
        </main>
      </div>
    )
  }

  // Caller has no family yet -> render onboarding card
  if (!familyData && !isSpecificFamily) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="family" />
        <main className="max-w-3xl w-full mx-auto px-4 py-12 flex-1 flex flex-col justify-center">
          <CreateFamilyCard
            onCreate={async (payload) => {
              await createMutation.mutateAsync(payload)
            }}
            isCreating={createMutation.isPending}
            currentLang={currentLang}
          />
        </main>
      </div>
    )
  }

  if (!familyData) {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900">
        <Nav active="family" />
        <main className="max-w-2xl w-full mx-auto px-6 py-16 text-center">
          <h1 className="text-lg font-bold text-slate-800">{t.family_not_found}</h1>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#F1F5FA] text-slate-900 antialiased">
      <Nav active="family" />

      {/* Top Header */}
      <section className="px-3.5 sm:px-6 pt-5 pb-3 max-w-[1400px] w-full mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold tracking-widest text-primary uppercase flex items-center gap-1.5">
              <HomeIcon className="size-3" />
              <span>{t.eyebrow}</span>
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight mt-0.5">
              {familyData.name}
            </h1>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5 flex-wrap">
              <span>
                {familyData.members.length} {t.members_count}
              </span>
              <span>·</span>
              <span>
                {familyData.check_counts.match} matched
              </span>
              {familyData.check_counts.conflict > 0 && (
                <>
                  <span>·</span>
                  <span className="text-destructive font-semibold">
                    {familyData.check_counts.conflict} conflict{familyData.check_counts.conflict === 1 ? "" : "s"}
                  </span>
                </>
              )}
            </p>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Language Selector */}
            {availableLanguages.length > 0 && (
              <div className="flex items-center gap-1 bg-white border border-border/90 rounded-lg px-2.5 py-1.5 text-xs shadow-2xs">
                <GlobeIcon className="size-3.5 text-muted-foreground shrink-0" />
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

            {/* Add Member button (Head only) */}
            {isHead && (
              <Button
                type="button"
                size="sm"
                onClick={() => setIsAddModalOpen(true)}
                className="h-8.5 px-3.5 text-xs font-bold gap-1.5 rounded-xl shadow-xs"
              >
                <UserPlusIcon className="size-3.5" />
                <span>{t.add_member}</span>
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="max-w-[1400px] w-full mx-auto px-3.5 sm:px-6 py-4 flex-1 flex flex-col gap-6">
        {/* Reviewer Notice (when viewer is not head) */}
        {!isHead && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/80 px-4 py-2.5 text-xs text-blue-900 flex items-center gap-2">
            <UsersIcon className="size-4 shrink-0 text-blue-700" />
            <span>{t.reviewer_banner}</span>
          </div>
        )}

        {/* Household Level Checks */}
        <FamilyChecksPanel
          checks={familyData.checks}
          checkCounts={familyData.check_counts}
          currentLang={currentLang}
        />

        {/* Members List */}
        <FamilyMembersList
          members={familyData.members}
          isHead={isHead}
          onEdit={(m) => setEditingMember(m)}
          onRemove={async (m) => {
            await removeMemberMutation.mutateAsync(m.id)
          }}
          isRemovingId={removingMemberId}
          currentLang={currentLang}
        />
      </main>

      {/* Add Member Modal */}
      <AddMemberModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={async (payload) => {
          await addMemberMutation.mutateAsync(payload)
        }}
        isSubmitting={addMemberMutation.isPending}
        currentLang={currentLang}
      />

      {/* Edit Member Modal */}
      <EditMemberModal
        member={editingMember}
        isOpen={Boolean(editingMember)}
        onClose={() => setEditingMember(null)}
        onUpdate={async (memberId, payload) => {
          await updateMemberMutation.mutateAsync({ memberId, payload })
        }}
        isSubmitting={updateMemberMutation.isPending}
        currentLang={currentLang}
      />
    </div>
  )
}
