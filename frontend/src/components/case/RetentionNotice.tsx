import { ClockIcon, FileXIcon, ShieldAlertIcon } from "lucide-react"

/** Whole days from now until `iso`; 0 when it is due or past. */
function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  if (Number.isNaN(ms)) return null
  return Math.max(0, Math.ceil(ms / 86_400_000))
}

/** Shown in place of the viewer once a document's stored file has been removed. */
export function FileRemovedNotice({ dataRemoved = false }: { dataRemoved?: boolean }) {
  return (
    <div
      role="status"
      className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center flex flex-col items-center gap-2"
    >
      <div className="p-2.5 rounded-full bg-slate-200 text-slate-600">
        <FileXIcon className="size-5" />
      </div>
      <p className="text-sm font-bold text-slate-800">This file has been removed</p>
      <p className="text-xs text-slate-600 max-w-sm">
        {dataRemoved
          ? "This was a private upload. Its files and everything read from them were removed when you signed out."
          : "Uploaded files are kept for a limited time and then removed automatically. The details read from this document are still shown here."}
      </p>
    </div>
  )
}

/** "File removed in N days" beside a document that is still stored. */
export function RetentionBadge({ expiresAt }: { expiresAt: string | null | undefined }) {
  const days = daysUntil(expiresAt)
  if (days === null) return null
  const soon = days <= 3
  return (
    <span
      title="Uploaded files are removed automatically. The details read from them are kept."
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
        soon ? "bg-amber-50 text-amber-900 border-amber-300" : "bg-slate-50 text-slate-600 border-slate-200"
      }`}
    >
      <ClockIcon className="size-3" />
      {days === 0 ? "File removed today" : `File removed in ${days} day${days === 1 ? "" : "s"}`}
    </span>
  )
}

/** Banner on a private case: what signing out will do, or that it already did. */
export function PrivateCaseBanner({ dataRemovedAt }: { dataRemovedAt: string | null | undefined }) {
  if (dataRemovedAt) {
    return (
      <div role="status" className="rounded-xl border border-slate-300 bg-slate-100 px-4 py-3 text-xs text-slate-800 flex items-start gap-2.5">
        <FileXIcon className="size-4 shrink-0 mt-0.5 text-slate-600" />
        <p>
          <span className="font-bold">This private upload has been emptied.</span> Its files and everything read from
          them were removed on {new Date(dataRemovedAt).toLocaleString()}. Only this record remains.
        </p>
      </div>
    )
  }
  return (
    <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-950 flex items-start gap-2.5">
      <ShieldAlertIcon className="size-4 shrink-0 mt-0.5 text-amber-700" />
      <p>
        <span className="font-bold">Private upload.</span> When you sign out, this case's files and everything read
        from them are removed for good. Note down anything you need before you sign out.
      </p>
    </div>
  )
}
