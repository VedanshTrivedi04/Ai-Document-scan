import * as React from "react"
import { FileIcon, UploadCloudIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { ACCEPTED_UPLOAD_TYPES_STRING, formatFileSize } from "@/lib/uploadLimits"
import { cn } from "@/lib/utils"

export interface FileWithProgress {
  file: File
  /** 0-100, or undefined before the upload for this file has started. */
  progress?: number
  error?: string
}

interface FileDropzoneProps {
  files: FileWithProgress[]
  onFilesAdded: (files: File[]) => void
  onFileRemoved: (index: number) => void
  disabled?: boolean
  /** The company's per-file limit; null while it loads. */
  maxFileBytes?: number | null
  /** File types accepted by the input dialog. */
  acceptedTypes?: string
  /** Custom hint text for file types, e.g. "PDF, JPG, PNG or TIFF". */
  hintText?: string
}

export function FileDropzone({
  files,
  onFilesAdded,
  onFileRemoved,
  disabled,
  maxFileBytes = null,
  acceptedTypes = ACCEPTED_UPLOAD_TYPES_STRING,
  hintText,
}: FileDropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [isDragActive, setIsDragActive] = React.useState(false)

  const openFileDialog = () => {
    if (!disabled) inputRef.current?.click()
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragActive(false)
    if (disabled) return
    const dropped = Array.from(event.dataTransfer.files)
    if (dropped.length > 0) onFilesAdded(dropped)
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        onClick={openFileDialog}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            openFileDialog()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setIsDragActive(true)
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          disabled
            ? "cursor-not-allowed opacity-50"
            : "cursor-pointer hover:bg-muted/40",
          isDragActive ? "border-accent bg-accent/5" : "border-border bg-muted/20"
        )}
      >
        <UploadCloudIcon className="size-8 text-muted-foreground" />
        <p className="text-sm font-medium">
          Drag and drop files here, or click to browse
        </p>
        <p className="text-xs text-muted-foreground">
          Attach every document supporting this case — e.g. an invoice and its
          approval voucher — in one go.
        </p>
        <p className="text-xs text-muted-foreground">
          {hintText ?? "PDF only"}
          {maxFileBytes !== null && <> · max file size: {formatFileSize(maxFileBytes)} each</>} ·
          not password-protected
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={acceptedTypes}
          disabled={disabled}
          className="hidden"
          onChange={(e) => {
            const selected = Array.from(e.target.files ?? [])
            if (selected.length > 0) onFilesAdded(selected)
            e.target.value = "" // allow re-selecting the same file later
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-col gap-2">
          {files.map(({ file, progress, error }, index) => {
            const isImage = file.type.startsWith("image/") || /\.(jpg|jpeg|png|tif|tiff)$/i.test(file.name)
            const isDone = progress === 100 && !error
            return (
              <li
                key={`${file.name}-${file.size}-${index}`}
                className="flex items-center gap-3 rounded-xl border bg-card p-2.5 text-sm shadow-2xs"
              >
                {isImage ? (
                  <div className="relative size-10 shrink-0 overflow-hidden rounded-lg border bg-muted/30">
                    <img
                      src={URL.createObjectURL(file)}
                      alt={file.name}
                      className="size-full object-cover"
                      onLoad={(e) => URL.revokeObjectURL((e.target as HTMLImageElement).src)}
                    />
                  </div>
                ) : (
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted/40 text-muted-foreground">
                    <FileIcon className="size-5" />
                  </div>
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="truncate font-semibold text-slate-800">{file.name}</span>
                      {isDone && (
                        <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                          Uploaded
                        </span>
                      )}
                      {error && (
                        <span className="shrink-0 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                          Failed
                        </span>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                  {progress !== undefined && !error && (
                    <Progress value={progress} className="h-1.5" />
                  )}
                  {error && <p className="text-xs text-destructive">{error}</p>}
                </div>
                {(progress === undefined || Boolean(error)) && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7 shrink-0 text-muted-foreground hover:text-slate-900"
                    disabled={disabled}
                    onClick={(e) => {
                      e.stopPropagation()
                      onFileRemoved(index)
                    }}
                    aria-label={`Remove ${file.name}`}
                  >
                    <XIcon className="size-4" />
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
