import { AlertTriangleIcon, CheckCircle2Icon, FileTextIcon, HomeIcon, Loader2Icon, PlusIcon } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import type { MyMembership } from "@/types/family"

interface MemberHomeProps {
  membership: MyMembership
}

/**
 * What a family member with a sign-in of their own sees: only their own
 * documents. The head manages the rest of the family.
 */
export function MemberHome({ membership }: MemberHomeProps) {
  const latest = membership.cases[0]

  return (
    <main className="max-w-3xl w-full mx-auto px-4 py-8 flex flex-col gap-5 font-sans">
      <div>
        <p className="text-[11px] font-bold tracking-widest text-primary uppercase flex items-center gap-1.5">
          <HomeIcon className="size-3" />
          <span>{membership.family_name}</span>
        </p>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-0.5">{membership.full_name}</h1>
        <p className="text-xs text-muted-foreground mt-1">
          Your family head manages your documents with you. You can add your own documents here.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <FileTextIcon className="size-4.5 text-primary" />
            <h2 className="text-sm font-bold">Your documents</h2>
            {membership.profile_ready === true ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                <CheckCircle2Icon className="size-3 text-emerald-600" />
                Profile ready
              </span>
            ) : membership.profile_ready === false ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-800 border border-red-200">
                <AlertTriangleIcon className="size-3 text-red-600" />
                Documents differ — your head will settle it
              </span>
            ) : null}
          </div>
          <Button asChild size="sm" className="h-8 text-xs font-bold gap-1.5 rounded-xl">
            <Link to="/cases/new">
              <PlusIcon className="size-3.5" />
              {latest ? "Add document" : "Upload documents"}
            </Link>
          </Button>
        </div>

        {membership.cases.length === 0 ? (
          <p className="text-xs text-muted-foreground italic rounded-lg bg-muted/30 border border-border/50 p-3">
            You have not uploaded any documents yet.
          </p>
        ) : (
          membership.cases.map((c) => (
            <div key={c.id} className="rounded-lg border border-border/60 bg-muted/20 p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <Link to={`/cases/${c.id}`} className="font-mono text-[11px] font-semibold text-primary hover:underline">
                  {c.case_number}
                </Link>
                <span className="text-[11px] text-muted-foreground">
                  {c.document_count} document{c.document_count === 1 ? "" : "s"}
                  {c.open_conflicts > 0 && (
                    <span className="text-destructive font-medium ml-1.5">· {c.open_conflicts} to settle</span>
                  )}
                </span>
              </div>
              {c.documents.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {c.documents.map((doc) => (
                    <li
                      key={doc.id}
                      className="flex items-center justify-between gap-2 text-[11px] rounded-md bg-background border border-border/60 px-2 py-1"
                    >
                      <span className="truncate font-medium" title={doc.filename}>
                        {doc.filename}
                      </span>
                      <span className="shrink-0 text-muted-foreground inline-flex items-center gap-1">
                        {doc.processing_status === "complete" ? (
                          (doc.document_type ?? "—")
                        ) : (
                          <>
                            <Loader2Icon className="size-3 animate-spin" />
                            Reading…
                          </>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        )}
      </div>
    </main>
  )
}
