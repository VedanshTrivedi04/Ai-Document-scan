import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Utility for merging Tailwind CSS class names conditionally.
 * Combines clsx (conditional class logic) with tailwind-merge (deduplication).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
