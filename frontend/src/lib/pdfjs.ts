/**
 * pdf.js configuration for react-pdf.
 *
 * Centralises the DocumentLoadOptions passed to every <Document> component
 * so that the worker URL, cmap, and font paths always stay in sync with
 * the installed pdfjs-dist version (served by the vite pdfjsAssets plugin
 * defined in vite.config.ts).
 */
import { pdfjs } from "react-pdf"

// Point the pdf.js web worker at the version shipped by pdfjs-dist.
// The file is served from /pdfjs/... by the pdfjsAssets vite plugin in dev,
// and copied into the production build by the same plugin.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString()

/**
 * Options passed to every react-pdf <Document> component.
 *
 * - cMapUrl / cMapPacked: required for correct rendering of CJK and other
 *   multi-byte character maps (the cmaps/ dir is served by the vite plugin).
 * - standardFontDataUrl: fallback for PDFs that embed no fonts of their own.
 */
export const PDF_DOCUMENT_OPTIONS = {
  cMapUrl: "/pdfjs/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "/pdfjs/standard_fonts/",
} as const
