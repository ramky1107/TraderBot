/**
 * api.js — All backend API calls.
 *
 * Exports:
 *   fetchStockData(ticker)       → fetches OHLCV + indicators, renders chart
 *   fetchLivePrice(ticker)       → fetches current price, updates sidebar
 *   fetchSentimentScore(ticker)  → fetches full sentiment, updates sidebar
 *   fetchFinancialRatios(ticker) → fetches ratios, updates sidebar
 */

import { API_URL } from './config.js';
import { updateStatus } from './status.js';
import { renderChart } from './chart.js';
import {
    renderSentimentScore,
    renderSignalActionBar,
    renderNewsHeadlines,
} from './renderers.js';
import * as dom from './dom.js';

// ─── Stock Data ───────────────────────────────────────────────────────────────

/**
 * Fetch OHLCV + indicator data and render the chart.
 * @param {string} ticker
 */
export async function fetchStockData(ticker) {
    const period = dom.periodSelect?.value || '5d';
    const interval = dom.intervalSelect?.value || '1d';

    try {
        updateStatus(`Fetching ${ticker} (${period}/${interval})…`);
        dom.fetchBtn?.classList.add('loading');

        const res = await fetch(
            `${API_URL}/api/stock-data?ticker=${encodeURIComponent(ticker)}&period=${period}&interval=${interval}`
        );
        const data = await res.json();

        if (!res.ok || data.error) {
            updateStatus(`Error: ${data.error || res.statusText}`);
            return;
        }

        renderChart(data);
        updateStatus(`${ticker} loaded — ${data.dates?.length || 0} bars`);

    } catch (err) {
        console.error('[api] fetchStockData', err);
        updateStatus(`Error: ${err.message}`);
    } finally {
        dom.fetchBtn?.classList.remove('loading');
    }
}

// ─── Live Price ───────────────────────────────────────────────────────────────

/**
 * Fetch and display the live price for a ticker.
 * @param {string} ticker
 */
export async function fetchLivePrice(ticker) {
    try {
        const res = await fetch(`${API_URL}/api/live-price?ticker=${encodeURIComponent(ticker)}`);
        const data = await res.json();

        if (!res.ok || data.error) return;

        if (dom.livePriceValue) {
            dom.livePriceValue.textContent = `₹${data.current_price?.toLocaleString('en-IN') || '--'}`;
        }

        const pct = data.change_pct ?? 0;
        const sign = pct >= 0 ? '+' : '';
        const cls = pct >= 0 ? 'positive' : 'negative';

        if (dom.livePriceChange) {
            dom.livePriceChange.textContent = `${sign}${pct.toFixed(2)}%`;
            dom.livePriceChange.className = `live-price-change ${cls}`;
        }

    } catch (err) {
        console.error('[api] fetchLivePrice', err);
    }
}

// ─── Sentiment Score ──────────────────────────────────────────────────────────

/**
 * Fetch full sentiment analysis and update the sidebar.
 * @param {string} ticker
 */
export async function fetchSentimentScore(ticker) {
    try {
        updateStatus(`Analyzing ${ticker}…`);
        dom.generateScoreBtn?.classList.add('loading');

        const res = await fetch(`${API_URL}/api/sentiment-score?ticker=${encodeURIComponent(ticker)}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            updateStatus(`Sentiment error: ${data.error}`);
            return;
        }

        renderSentimentScore(data);
        renderSignalActionBar(data.signals || []);
        renderNewsHeadlines(data.news?.headlines || []);

        updateStatus(`Analysis complete — ${data.label}`);

    } catch (err) {
        console.error('[api] fetchSentimentScore', err);
        updateStatus(`Error: ${err.message}`);
    } finally {
        dom.generateScoreBtn?.classList.remove('loading');
    }
}

// ─── Financial Ratios ─────────────────────────────────────────────────────────

/**
 * Fetch financial ratios and populate the sidebar.
 * @param {string} ticker
 */
export async function fetchFinancialRatios(ticker) {
    try {
        const res = await fetch(`${API_URL}/api/financial-ratios?ticker=${encodeURIComponent(ticker)}`);
        const data = await res.json();

        if (!res.ok || data.error) return;

        const r = data.ratios || {};
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val || '--';
        };

        set('peRatio', r.pe_ratio);
        set('pbRatio', r.pb_ratio);
        set('debtEquity', r.debt_equity);
        set('marketCap', r.market_cap);
        set('dividendYield', r.dividend_yield);
        set('roeValue', r.roe);
        set('epsValue', r.eps);
        set('bookValue', r.book_value);

    } catch (err) {
        console.error('[api] fetchFinancialRatios', err);
    }
}
