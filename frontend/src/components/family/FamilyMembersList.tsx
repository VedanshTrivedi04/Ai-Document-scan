import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  Edit2Icon,
  FileTextIcon,
  KeyRoundIcon,
  Loader2Icon,
  PlusIcon,
  PowerIcon,
  Trash2Icon,
  UploadIcon,
  UserCheck2Icon,
  UserXIcon,
  UsersIcon,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import type { FamilyMember } from "@/types/family"

interface FamilyMembersListProps {
  members: FamilyMember[]
  isHead: boolean
  onEdit: (member: FamilyMember) => void
  onRemove: (member: FamilyMember) => Promise<void>
  isRemovingId?: string | null
  currentLang?: string
  /** Sign-in management (head only). */
  onCreateLogin?: (member: FamilyMember) => void
  onResetPassword?: (member: FamilyMember) => Promise<void>
  onToggleLogin?: (member: FamilyMember, isActive: boolean) => Promise<void>
  onRemoveLogin?: (member: FamilyMember) => Promise<void>
  busyLoginId?: string | null
}

const MEMBERS_I18N: Record<string, Record<string, string>> = {
  en: {
    title: "Household members",
    subtitle: "Each family member can have one or more document bundles verified.",
    head_badge: "Head of family",
    no_bundle: "No documents submitted yet",
    upload_bundle: "Upload documents",
    view_case: "View case",
    profile_ready: "Profile ready",
    profile_conflicts: "Document conflicts",
    reading_docs: "Reading documents…",
    born: "Born",
    docs: "docs",
    conflicts_count: "open conflicts",
    edit: "Edit",
    remove: "Remove",
    remove_confirm: "Are you sure you want to remove this member?",
    head_locked_tooltip: "The head of the family cannot be removed.",
    case_locked_tooltip: "This member already has documents submitted and cannot be removed.",
    add_document: "Add document",
    documents: "Documents",
    manage_documents: "Manage documents",
    login_none: "No sign-in",
    login_active: "Can sign in",
    login_off: "Sign-in off",
    login_temp: "Must choose password",
    create_login: "Create sign-in",
    reset_password: "Reset password",
    reset_confirm: "Set a new temporary password for this person? Their old password stops working.",
    switch_off: "Switch off",
    switch_on: "Switch on",
    remove_login: "Remove sign-in",
    remove_login_confirm: "Remove this person's sign-in? They will no longer be able to sign in. Their documents stay.",
    processing: "Reading…",
  },
  hi: {
    title: "परिवार के सदस्य",
    subtitle: "प्रत्येक पारिवारिक सदस्य के लिए एक या अधिक दस्तावेज़ बंडल सत्यापित किए जा सकते हैं।",
    head_badge: "परिवार का मुखिया",
    no_bundle: "अभी तक कोई दस्तावेज़ जमा नहीं किया गया",
    upload_bundle: "दस्तावेज़ अपलोड करें",
    view_case: "मामला देखें",
    profile_ready: "प्रोफ़ाइल तैयार",
    profile_conflicts: "दस्तावेज़ों में अंतर",
    reading_docs: "दस्तावेज़ पढ़े जा रहे हैं…",
    born: "जन्म",
    docs: "दस्तावेज़",
    conflicts_count: "लंबित विरोधाभास",
    edit: "संशोधित करें",
    remove: "हटाएं",
    remove_confirm: "क्या आप वाकई इस सदस्य को हटाना चाहते हैं?",
    head_locked_tooltip: "परिवार के मुखिया को हटाया नहीं जा सकता।",
    case_locked_tooltip: "इस सदस्य के दस्तावेज़ पहले ही जमा हो चुके हैं, इसलिए इन्हें हटाया नहीं जा सकता।",
    add_document: "दस्तावेज़ जोड़ें",
    documents: "दस्तावेज़",
    manage_documents: "दस्तावेज़ संभालें",
    login_none: "साइन-इन नहीं है",
    login_active: "साइन-इन कर सकते हैं",
    login_off: "साइन-इन बंद",
    login_temp: "पासवर्ड बदलना बाकी",
    create_login: "साइन-इन बनाएँ",
    reset_password: "पासवर्ड रीसेट करें",
    reset_confirm: "क्या इस व्यक्ति के लिए नया अस्थायी पासवर्ड बनाना है? पुराना पासवर्ड काम करना बंद कर देगा।",
    switch_off: "बंद करें",
    switch_on: "चालू करें",
    remove_login: "साइन-इन हटाएँ",
    remove_login_confirm: "क्या इस व्यक्ति का साइन-इन हटाना है? वे साइन-इन नहीं कर पाएँगे। उनके दस्तावेज़ बने रहेंगे।",
    processing: "पढ़ा जा रहा है…",
  },
}

export function FamilyMembersList({
  members,
  isHead,
  onEdit,
  onRemove,
  isRemovingId,
  currentLang = "en",
  onCreateLogin,
  onResetPassword,
  onToggleLogin,
  onRemoveLogin,
  busyLoginId,
}: FamilyMembersListProps) {
  const langKey = currentLang === "hi" ? "hi" : "en"
  const t = MEMBERS_I18N[langKey] ?? MEMBERS_I18N.en

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-border/80">
        <div>
          <div className="flex items-center gap-2">
            <UsersIcon className="size-4.5 text-primary" />
            <h3 className="text-sm font-bold text-foreground">{t.title}</h3>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">{t.subtitle}</p>
        </div>
      </div>

      {/* Members Grid / List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {members.map((member) => {
          const hasCase = Boolean(member.latest_case_id)
          const latestCase = member.cases[0]
          const isRemovingThis = isRemovingId === member.id

          return (
            <div
              key={member.id}
              className="p-4 rounded-xl border border-border/80 bg-background flex flex-col justify-between gap-3 text-xs hover:border-primary/30 transition-all shadow-2xs"
            >
              {/* Member Identity Details */}
              <div className="flex flex-col gap-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold text-foreground text-sm truncate">
                        {member.full_name}
                      </span>
                      {member.is_head && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-primary text-primary-foreground">
                          <UserCheck2Icon className="size-3" />
                          {t.head_badge}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-0.5 flex-wrap">
                      <span className="font-semibold text-foreground/80">
                        {member.relation_label}
                      </span>
                      {member.date_of_birth && (
                        <>
                          <span>·</span>
                          <span>
                            {t.born}: {member.date_of_birth}
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Edit / Remove actions for head */}
                  {isHead && (
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        onClick={() => onEdit(member)}
                        className="size-7 text-muted-foreground hover:text-foreground"
                        title={t.edit}
                      >
                        <Edit2Icon className="size-3.5" />
                      </Button>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        disabled={member.is_head || member.cases.length > 0 || isRemovingThis}
                        onClick={() => {
                          if (window.confirm(t.remove_confirm)) {
                            onRemove(member)
                          }
                        }}
                        className="size-7 text-muted-foreground hover:text-destructive disabled:opacity-30 disabled:hover:text-muted-foreground"
                        title={
                          member.is_head
                            ? t.head_locked_tooltip
                            : member.cases.length > 0
                            ? t.case_locked_tooltip
                            : t.remove
                        }
                      >
                        {isRemovingThis ? (
                          <Loader2Icon className="size-3.5 animate-spin" />
                        ) : (
                          <Trash2Icon className="size-3.5" />
                        )}
                      </Button>
                    </div>
                  )}
                </div>

                {/* Case / Bundle Status Block */}
                <div className="mt-1 pt-2.5 border-t border-border/60 flex flex-col gap-2">
                  {!hasCase ? (
                    <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-muted/30 border border-border/50">
                      <span className="text-[11px] text-muted-foreground italic">
                        {t.no_bundle}
                      </span>
                      {isHead && (
                        <Button
                          asChild
                          size="sm"
                          variant="outline"
                          className="h-6 text-[11px] font-semibold gap-1 px-2"
                        >
                          <Link to={`/cases/new?family_member_id=${member.id}`}>
                            <UploadIcon className="size-3" />
                            <span>{t.upload_bundle}</span>
                          </Link>
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1.5 p-2.5 rounded-lg bg-muted/20 border border-border/60">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <Link
                          to={`/cases/${member.latest_case_id}`}
                          className="font-mono font-semibold text-primary hover:underline flex items-center gap-1 text-[11px]"
                        >
                          <FileTextIcon className="size-3 shrink-0" />
                          <span>{latestCase?.case_number}</span>
                        </Link>

                        {/* Profile Readiness Pill */}
                        {member.profile_ready === true ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                            <CheckCircle2Icon className="size-3 text-emerald-600" />
                            {t.profile_ready}
                          </span>
                        ) : member.profile_ready === false ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-800 border border-red-200">
                            <AlertTriangleIcon className="size-3 text-red-600" />
                            {t.profile_conflicts}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                            <Loader2Icon className="size-2.5 animate-spin" />
                            {t.reading_docs}
                          </span>
                        )}
                      </div>

                      {latestCase && latestCase.documents.length > 0 && (
                        <ul className="mt-1 flex flex-col gap-1" aria-label={t.documents}>
                          {latestCase.documents.map((doc) => (
                            <li
                              key={doc.id}
                              className="flex items-center justify-between gap-2 text-[11px] rounded-md bg-background border border-border/60 px-2 py-1"
                            >
                              <span className="truncate font-medium text-foreground/90" title={doc.filename}>
                                {doc.filename}
                              </span>
                              <span className="shrink-0 text-muted-foreground">
                                {doc.processing_status === "complete" ? (doc.document_type ?? "—") : t.processing}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}

                      <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground mt-0.5">
                        <span>
                          {latestCase?.document_count} {t.docs}
                          {latestCase && latestCase.open_conflicts > 0 && (
                            <span className="text-destructive font-medium ml-1.5">
                              · {latestCase.open_conflicts} {t.conflicts_count}
                            </span>
                          )}
                        </span>
                        <Link
                          to={`/cases/${member.latest_case_id}`}
                          className="font-semibold text-primary hover:underline text-[11px]"
                        >
                          {isHead ? t.manage_documents : t.view_case} →
                        </Link>
                      </div>
                      {isHead && (
                        <Button
                          asChild
                          size="sm"
                          variant="outline"
                          className="h-6 text-[11px] font-semibold gap-1 px-2 self-start"
                        >
                          <Link to={`/cases/new?family_member_id=${member.id}`}>
                            <PlusIcon className="size-3" />
                            <span>{t.add_document}</span>
                          </Link>
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {/* Sign-in (head manages it; the head's own entry has none) */}
                {isHead && !member.is_head && (
                  <div className="pt-2.5 border-t border-border/60 flex flex-col gap-1.5">
                    {member.login ? (
                      <>
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span className="text-[11px] text-muted-foreground truncate" title={member.login.email}>
                            {member.login.email}
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              !member.login.is_active
                                ? "bg-slate-100 text-slate-700 border-slate-200"
                                : member.login.must_change_password
                                  ? "bg-amber-50 text-amber-800 border-amber-200"
                                  : "bg-emerald-50 text-emerald-800 border-emerald-200"
                            }`}
                          >
                            {!member.login.is_active
                              ? t.login_off
                              : member.login.must_change_password
                                ? t.login_temp
                                : t.login_active}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 flex-wrap">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={busyLoginId === member.id}
                            onClick={() => {
                              if (window.confirm(t.reset_confirm)) void onResetPassword?.(member)
                            }}
                            className="h-6 px-2 text-[11px] gap-1"
                          >
                            <KeyRoundIcon className="size-3" />
                            {t.reset_password}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={busyLoginId === member.id}
                            onClick={() => void onToggleLogin?.(member, !member.login!.is_active)}
                            className="h-6 px-2 text-[11px] gap-1"
                          >
                            <PowerIcon className="size-3" />
                            {member.login.is_active ? t.switch_off : t.switch_on}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={busyLoginId === member.id}
                            onClick={() => {
                              if (window.confirm(t.remove_login_confirm)) void onRemoveLogin?.(member)
                            }}
                            className="h-6 px-2 text-[11px] gap-1 text-destructive hover:text-destructive"
                          >
                            <UserXIcon className="size-3" />
                            {t.remove_login}
                          </Button>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] text-muted-foreground italic">{t.login_none}</span>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => onCreateLogin?.(member)}
                          className="h-6 text-[11px] font-semibold gap-1 px-2"
                        >
                          <KeyRoundIcon className="size-3" />
                          {t.create_login}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
