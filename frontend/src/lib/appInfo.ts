/**
 * Single source of truth for product name constants.
 * Consumed by vite.config.ts (at build time) and throughout the app.
 */

export const APP_NAME = "DocSure"

export const APP_FULL_NAME = "AI Document Authentication Platform"

/** Title used in <title> tags and browser tab. */
export const APP_TITLE = `${APP_NAME} — ${APP_FULL_NAME}`
