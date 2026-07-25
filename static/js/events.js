/**
 * events.js — Top-level event handlers and event wiring.
 *
 * Imports all action modules and connects them to DOM events.
 * Called once by main.js after all partials are loaded and dom.js is populated.
 */

import * as dom from './dom.js';
import {
    DEFAULT_TICKER,
    LIVE_PRICE_POLL_MS
} from './config.js';
import {
    getLivePriceInterval,
    setLivePriceInterval,
} from './state.js';
import {
    fetchStockData,
    fetchLivePrice,
    fetchSentimentScore,
    fetchFinancialRatios,
} from './api.js';
import { initIndicatorToggles } from './indicators-toggle.js';
import { initWebSocket } from './websocket.js';
import { initChatbot } from './chatbot.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Return the current ticker from the input (uppercased, trimmed). */
function getTicker() {
    return (dom.tickerInput?.value || DEFAULT_TICKER).trim().toUpperCase();
}

// ─── Handlers ─────────────────────────────────────────────────────────────────

/** "Update Chart" button / Enter key in ticker input. */
export function onFetchButtonClick() {
    const ticker = getTicker();
    if (!ticker) return;
    if (dom.tickerInput) dom.tickerInput.value = ticker;

    // Read period/interval directly from the live DOM elements.
    // We query by ID here (not via dom module refs) to guarantee we always
    // get the current select value regardless of module binding timing.
    const period = document.getElementById('periodSelect')?.value || '5d';
    const interval = document.getElementById('intervalSelect')?.value || '1d';

    // Reset live-price polling for the new ticker
    const prev = getLivePriceInterval();
    if (prev) clearInterval(prev);

    fetchStockData(ticker, period, interval);
    fetchLivePrice(ticker);

    setLivePriceInterval(
        setInterval(() => fetchLivePrice(ticker), LIVE_PRICE_POLL_MS)
    );
}

/** "Generate Score" button. */
export function onGenerateScoreClick() {
    const ticker = getTicker();
    if (!ticker) return;

    fetchSentimentScore(ticker);
    fetchFinancialRatios(ticker);
    initWebSocket(ticker);
}

// ─── Wire All Events ──────────────────────────────────────────────────────────

/**
 * Attach all event listeners.
 * Must be called after dom.populate() has resolved all references.
 */
export function wireEvents() {
    // Toolbar
    dom.fetchBtn?.addEventListener('click', onFetchButtonClick);
    dom.generateScoreBtn?.addEventListener('click', onGenerateScoreClick);
    dom.tickerInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter') onFetchButtonClick();
    });

    // Period / interval selects re-fetch the chart
    dom.periodSelect?.addEventListener('change', onFetchButtonClick);
    dom.intervalSelect?.addEventListener('change', onFetchButtonClick);

    // Indicator toggle pills
    initIndicatorToggles();

    // Chatbot
    initChatbot();
}
