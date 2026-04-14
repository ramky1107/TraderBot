/**
 * config.js — Application-wide constants.
 * Import this wherever you need the API base URL or defaults.
 */

/** Flask backend base URL */
export const API_URL = window.location.origin;

/** Default ticker shown on startup */
export const DEFAULT_TICKER = '^NSEI';

/** Live price polling interval in milliseconds */
export const LIVE_PRICE_POLL_MS = 30_000;
