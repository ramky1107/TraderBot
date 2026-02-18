/**
 * main.js — Application entry point.
 *
 * Boot sequence:
 *   1. Load all HTML partials in parallel (loader.js)
 *   2. Populate DOM references (dom.js)
 *   3. Wire all event listeners (events.js)
 *   4. Kick off the default chart + live-price polling
 *
 * This is the only file referenced by index.html as type="module".
 */

import { loadAllPartials } from './loader.js';
import { populate as populateDom } from './dom.js';
import {
    wireEvents,
    onFetchButtonClick
} from './events.js';
import { fetchLivePrice } from './api.js';
import { setLivePriceInterval } from './state.js';
import {
    DEFAULT_TICKER,
    LIVE_PRICE_POLL_MS
} from './config.js';

async function boot() {
    // ── Step 1: Inject all HTML partials ──────────────────────────────────────
    await loadAllPartials();

    // ── Step 2: Resolve DOM references ────────────────────────────────────────
    populateDom();

    // ── Step 3: Wire events ───────────────────────────────────────────────────
    wireEvents();

    // ── Step 4: Load default chart ────────────────────────────────────────────
    onFetchButtonClick();   // uses tickerInput.value (set to DEFAULT_TICKER in toolbar.html)

    // Start live-price polling for the default ticker
    setLivePriceInterval(
        setInterval(() => fetchLivePrice(DEFAULT_TICKER), LIVE_PRICE_POLL_MS)
    );
}

// Run after the shell DOM is ready (partials are fetched, not yet in DOM)
document.addEventListener('DOMContentLoaded', boot);
