import * as React from "react"
import {
  CameraIcon,
  Loader2Icon,
  Maximize2Icon,
  AlertCircleIcon,
} from "lucide-react"
import { pdfjs } from "react-pdf"
import { PDF_DOCUMENT_OPTIONS } from "@/lib/pdfjs"
import { cn } from "@/lib/utils"
import type { BoundingBox } from "@/types/case"

export interface FaceCropThumbnailProps {
  fileUrl?: string
  originalFilename?: string
  contentType?: string | null
  boundingBox?: BoundingBox | null
  alt?: string
  className?: string
  onClick?: () => void
  size?: "sm" | "md" | "lg"
}

// In-memory LRU cache so repeated renders/toggles don't re-crop the canvas
const cropCache = new Map<string, string>()

function isImage(url?: string, filename?: string, contentType?: string | null): boolean {
  if (contentType?.startsWith("image/")) return true
  const target = (filename || url || "").split("?")[0].toLowerCase()
  return (
    target.endsWith(".jpg") ||
    target.endsWith(".jpeg") ||
    target.endsWith(".png") ||
    target.endsWith(".webp") ||
    target.endsWith(".bmp") ||
    target.endsWith(".tif") ||
    target.endsWith(".tiff")
  )
}

function cropFromImage(
  img: HTMLImageElement,
  box: BoundingBox,
  targetWidth = 320,
  targetHeight = 380
): string {
  // Give comfortable margins around the face so it looks like a natural ID portrait
  const padX = box.width * 0.25
  const padYTop = box.height * 0.35
  const padYBottom = box.height * 0.25

  const cropX = Math.max(0, box.x - padX)
  const cropY = Math.max(0, box.y - padYTop)
  const cropW = Math.min(1 - cropX, box.width + padX * 2)
  const cropH = Math.min(1 - cropY, box.height + padYTop + padYBottom)

  const sx = Math.max(0, Math.round(cropX * img.naturalWidth))
  const sy = Math.max(0, Math.round(cropY * img.naturalHeight))
  const sw = Math.min(img.naturalWidth - sx, Math.round(cropW * img.naturalWidth))
  const sh = Math.min(img.naturalHeight - sy, Math.round(cropH * img.naturalHeight))

  if (sw <= 0 || sh <= 0) return ""

  const canvas = document.createElement("canvas")
  canvas.width = targetWidth
  canvas.height = targetHeight
  const ctx = canvas.getContext("2d")
  if (!ctx) return ""

  // Fill subtle portrait background
  ctx.fillStyle = "#f8fafc"
  ctx.fillRect(0, 0, targetWidth, targetHeight)

  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = "high"
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, targetWidth, targetHeight)

  return canvas.toDataURL("image/jpeg", 0.92)
}

async function cropFromPdf(
  fileUrl: string,
  box: BoundingBox,
  targetWidth = 320,
  targetHeight = 380
): Promise<string> {
  const pageNum = Math.max(1, box.page || 1)
  const loadingTask = pdfjs.getDocument({ url: fileUrl, ...PDF_DOCUMENT_OPTIONS })
  const pdfDoc = await loadingTask.promise
  const page = await pdfDoc.getPage(pageNum)

  // Render at 2x scale for sharp face crop
  const viewport = page.getViewport({ scale: 2.0 })
  const pageCanvas = document.createElement("canvas")
  pageCanvas.width = Math.round(viewport.width)
  pageCanvas.height = Math.round(viewport.height)
  const pageCtx = pageCanvas.getContext("2d")
  if (!pageCtx) throw new Error("Could not get canvas context")

  await (page.render as any)({ canvasContext: pageCtx, viewport, canvas: pageCanvas }).promise

  const padX = box.width * 0.25
  const padYTop = box.height * 0.35
  const padYBottom = box.height * 0.25

  const cropX = Math.max(0, box.x - padX)
  const cropY = Math.max(0, box.y - padYTop)
  const cropW = Math.min(1 - cropX, box.width + padX * 2)
  const cropH = Math.min(1 - cropY, box.height + padYTop + padYBottom)

  const sx = Math.max(0, Math.round(cropX * pageCanvas.width))
  const sy = Math.max(0, Math.round(cropY * pageCanvas.height))
  const sw = Math.min(pageCanvas.width - sx, Math.round(cropW * pageCanvas.width))
  const sh = Math.min(pageCanvas.height - sy, Math.round(cropH * pageCanvas.height))

  if (sw <= 0 || sh <= 0) return ""

  const canvas = document.createElement("canvas")
  canvas.width = targetWidth
  canvas.height = targetHeight
  const ctx = canvas.getContext("2d")
  if (!ctx) return ""

  ctx.fillStyle = "#f8fafc"
  ctx.fillRect(0, 0, targetWidth, targetHeight)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = "high"
  ctx.drawImage(pageCanvas, sx, sy, sw, sh, 0, 0, targetWidth, targetHeight)

  return canvas.toDataURL("image/jpeg", 0.92)
}

export function FaceCropThumbnail({
  fileUrl,
  originalFilename,
  contentType,
  boundingBox,
  alt = "Detected face portrait",
  className,
  onClick,
  size = "md",
}: FaceCropThumbnailProps) {
  const [dataUrl, setDataUrl] = React.useState<string | null>(null)
  const [isLoading, setIsLoading] = React.useState<boolean>(true)
  const [hasError, setHasError] = React.useState<boolean>(false)

  const cacheKey = React.useMemo(() => {
    if (!fileUrl || !boundingBox) return null
    return `${fileUrl}_${boundingBox.page ?? 1}_${boundingBox.x}_${boundingBox.y}_${boundingBox.width}_${boundingBox.height}`
  }, [fileUrl, boundingBox])

  React.useEffect(() => {
    if (!fileUrl) {
      setIsLoading(false)
      setHasError(true)
      return
    }

    if (!boundingBox) {
      setIsLoading(false)
      return
    }

    if (cacheKey && cropCache.has(cacheKey)) {
      setDataUrl(cropCache.get(cacheKey)!)
      setIsLoading(false)
      setHasError(false)
      return
    }

    let isMounted = true
    setIsLoading(true)
    setHasError(false)

    const isImg = isImage(fileUrl, originalFilename, contentType)

    if (isImg) {
      const img = new Image()
      img.crossOrigin = "anonymous"
      img.onload = () => {
        if (!isMounted) return
        try {
          const cropped = cropFromImage(img, boundingBox)
          if (cropped) {
            if (cacheKey) cropCache.set(cacheKey, cropped)
            setDataUrl(cropped)
          } else {
            setHasError(true)
          }
        } catch (e) {
          console.warn("Failed to crop face from image:", e)
          setHasError(true)
        } finally {
          setIsLoading(false)
        }
      }
      img.onerror = () => {
        if (!isMounted) return
        setHasError(true)
        setIsLoading(false)
      }
      img.src = fileUrl
    } else {
      // PDF source
      cropFromPdf(fileUrl, boundingBox)
        .then((cropped) => {
          if (!isMounted) return
          if (cropped) {
            if (cacheKey) cropCache.set(cacheKey, cropped)
            setDataUrl(cropped)
          } else {
            setHasError(true)
          }
        })
        .catch((err) => {
          if (!isMounted) return
          console.warn("Failed to crop face from PDF:", err)
          setHasError(true)
        })
        .finally(() => {
          if (isMounted) setIsLoading(false)
        })
    }

    return () => {
      isMounted = false
    }
  }, [fileUrl, originalFilename, contentType, boundingBox, cacheKey])

  const sizeClasses = {
    sm: "w-20 h-24 sm:w-24 sm:h-28",
    md: "w-28 h-36 sm:w-32 sm:h-40",
    lg: "w-36 h-44 sm:w-44 sm:h-52",
  }[size]

  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault()
          onClick()
        }
      }}
      className={cn(
        "group relative flex flex-col items-center justify-center overflow-hidden rounded-xl border border-border/80 bg-muted/20 shadow-2xs transition-all",
        onClick && "cursor-pointer hover:border-primary/60 hover:shadow-md",
        sizeClasses,
        className
      )}
      title={onClick ? "Click to view highlighted in document" : alt}
    >
      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center gap-1.5 p-2 text-center text-muted-foreground animate-pulse">
          <Loader2Icon className="size-5 animate-spin text-primary" />
          <span className="text-[10px] font-medium">Extracting photo…</span>
        </div>
      )}

      {/* No Bounding Box / Not Detected State */}
      {!isLoading && !boundingBox && (
        <div className="flex flex-col items-center justify-center gap-1 p-2 text-center text-muted-foreground">
          <div className="rounded-full bg-muted p-2">
            <CameraIcon className="size-5 text-muted-foreground/70" />
          </div>
          <span className="text-[10px] font-medium leading-tight">No face region detected</span>
        </div>
      )}

      {/* Error State */}
      {!isLoading && boundingBox && (hasError || !dataUrl) && (
        <div className="flex flex-col items-center justify-center gap-1 p-2 text-center text-muted-foreground">
          <div className="rounded-full bg-destructive/10 p-2 text-destructive">
            <AlertCircleIcon className="size-5" />
          </div>
          <span className="text-[10px] font-medium leading-tight text-destructive">
            Couldn&apos;t crop photo
          </span>
        </div>
      )}

      {/* Success Image State */}
      {!isLoading && dataUrl && (
        <>
          <img
            src={dataUrl}
            alt={alt}
            className="size-full object-cover transition-transform duration-200 group-hover:scale-105"
          />

          {/* Hover Overlay with expand hint */}
          {onClick && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 backdrop-blur-[1px] transition-opacity duration-200 group-hover:opacity-100">
              <span className="inline-flex items-center gap-1 rounded-full bg-background/90 px-2 py-1 text-[11px] font-semibold text-foreground shadow-xs">
                <Maximize2Icon className="size-3 text-primary" />
                Inspect
              </span>
            </div>
          )}
        </>
      )}

      {/* Face indicator badge */}
      {!isLoading && dataUrl && (
        <div className="absolute top-1.5 left-1.5 rounded-md bg-background/80 px-1.5 py-0.5 text-[9px] font-semibold text-foreground/80 backdrop-blur-xs border border-border/50 pointer-events-none shadow-2xs">
          Face Crop
        </div>
      )}
    </div>
  )
}
