/**
 * chart.js — Unified single-panel Plotly chart.
 *
 * Exports:
 *   buildCandlestickTrace(data)        → Plotly trace object
 *   buildIndicatorTraces(data)         → Array of Plotly trace objects
 *   buildChartLayout(data, ticker)     → Plotly layout object
 *   renderChart(data)                  → Renders / updates the chart
 */

import { activeIndicators, setLastChartData } from './state.js';
import { updateStatus } from './status.js';
import * as dom from './dom.js';

// ─── Candlestick ──────────────────────────────────────────────────────────────

/**
 * Build the always-visible candlestick trace.
 * @param {Object} data - /api/stock-data response
 * @returns {Object} Plotly trace
 */
export function buildCandlestickTrace(data) {
    return {
        type: 'candlestick',
        x: data.dates,
        open: data.open,
        high: data.high,
        low: data.low,
        close: data.close,
        name: 'OHLC',
        yaxis: 'y',
        increasing: { line: { color: '#26a69a', width: 1 }, fillcolor: '#26a69a' },
        decreasing: { line: { color: '#ef5350', width: 1 }, fillcolor: '#ef5350' },
        whiskerwidth: 0.5,
    };
}

// ─── Indicator Traces ─────────────────────────────────────────────────────────

/**
 * Build all active indicator overlay traces.
 *
 * y-axis assignments:
 *   y  → price scale (SMA, BB)
 *   y2 → RSI  0–100 (right)
 *   y3 → Volume (right, scaled to bottom 20%)
 *   y4 → MACD (right)
 *
 * @param {Object} data - /api/stock-data response
 * @returns {Array<Object>} Plotly traces
 */
export function buildIndicatorTraces(data) {
    const traces = [];

    // ── SMA 20 ────────────────────────────────────────────────────────────────
    if (activeIndicators.has('sma20') && data.sma_20?.length) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.sma_20,
            name: 'SMA 20', yaxis: 'y',
            line: { color: '#f39c12', width: 1.5 },
        });
    }

    // ── SMA 50 ────────────────────────────────────────────────────────────────
    if (activeIndicators.has('sma50') && data.sma_50?.length) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.sma_50,
            name: 'SMA 50', yaxis: 'y',
            line: { color: '#9b59b6', width: 1.5 },
        });
    }

    // ── Bollinger Bands ───────────────────────────────────────────────────────
    if (activeIndicators.has('bb') && data.bb_upper?.length) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.bb_upper,
            name: 'BB Upper', yaxis: 'y',
            line: { color: 'rgba(52,152,219,0.6)', width: 1, dash: 'dot' },
            showlegend: true,
        });
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.bb_lower,
            name: 'BB Lower', yaxis: 'y',
            line: { color: 'rgba(52,152,219,0.6)', width: 1, dash: 'dot' },
            fill: 'tonexty', fillcolor: 'rgba(52,152,219,0.05)',
            showlegend: false,
        });
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.bb_middle,
            name: 'BB Mid', yaxis: 'y',
            line: { color: 'rgba(52,152,219,0.4)', width: 1 },
            showlegend: false,
        });
    }

    // ── RSI ───────────────────────────────────────────────────────────────────
    if (activeIndicators.has('rsi') && data.rsi?.length) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.rsi,
            name: 'RSI (14)', yaxis: 'y2',
            line: { color: '#e74c3c', width: 1.5 },
        });
        // Reference lines at 70 / 30
        const xEnds = [data.dates[0], data.dates[data.dates.length - 1]];
        traces.push({
            type: 'scatter', mode: 'lines',
            x: xEnds, y: [70, 70], name: 'RSI 70', yaxis: 'y2',
            line: { color: 'rgba(231,76,60,0.3)', width: 1, dash: 'dash' },
            showlegend: false,
        });
        traces.push({
            type: 'scatter', mode: 'lines',
            x: xEnds, y: [30, 30], name: 'RSI 30', yaxis: 'y2',
            line: { color: 'rgba(39,174,96,0.3)', width: 1, dash: 'dash' },
            showlegend: false,
        });
    }

    // ── MACD ──────────────────────────────────────────────────────────────────
    if (activeIndicators.has('macd') && data.macd?.length) {
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.macd,
            name: 'MACD', yaxis: 'y4',
            line: { color: '#1abc9c', width: 1.5 },
        });
        traces.push({
            type: 'scatter', mode: 'lines',
            x: data.dates, y: data.macd_signal,
            name: 'MACD Signal', yaxis: 'y4',
            line: { color: '#e67e22', width: 1, dash: 'dot' },
        });
    }

    // ── Volume ────────────────────────────────────────────────────────────────
    if (activeIndicators.has('volume') && data.volume?.length) {
        traces.push({
            type: 'bar',
            x: data.dates, y: data.volume,
            name: 'Volume', yaxis: 'y3',
            marker: { color: 'rgba(100,149,237,0.35)' },
        });
    }

    return traces;
}

// ─── Layout ───────────────────────────────────────────────────────────────────

/**
 * Build the Plotly layout for the unified chart.
 * @param {Object} data   - /api/stock-data response
 * @param {string} ticker
 * @returns {Object} Plotly layout
 */
export function buildChartLayout(data, ticker) {
    const lastClose = data.close?.length ? data.close[data.close.length - 1] : 0;

    const maxVol = data.volume?.length
        ? Math.max(...data.volume.filter(v => v != null))
        : 1;

    const prices = [...(data.high || []), ...(data.low || [])].filter(v => v != null);
    const minPrice = prices.length ? Math.min(...prices) : 0;
    const maxPrice = prices.length ? Math.max(...prices) : 1;
    const priceRange = maxPrice - minPrice;

    return {
        title: {
            text: `${ticker} — Last: ${lastClose?.toFixed ? lastClose.toFixed(2) : lastClose}`,
            font: { size: 14, family: 'Inter, Ubuntu, sans-serif', color: '#D1D4DC' },
            x: 0.01,
            xanchor: 'left',
        },
        paper_bgcolor: '#000000',
        plot_bgcolor: '#000000',
        font: { family: 'Inter, Ubuntu, sans-serif', color: '#D1D4DC', size: 11 },
        margin: { l: 60, r: 80, t: 40, b: 40 },
        height: null,
        hovermode: 'x unified',
        hoverlabel: { bgcolor: '#1a1a2e', font: { color: '#D1D4DC' } },
        legend: {
            orientation: 'h', yanchor: 'bottom', y: 1.01,
            xanchor: 'right', x: 1, font: { size: 10 },
            bgcolor: 'rgba(0,0,0,0)',
        },
        xaxis: {
            rangeslider: { visible: false },
            gridcolor: '#111111',
            linecolor: '#222222',
            tickfont: { size: 10 },
            rangebreaks: [{ bounds: ['sat', 'mon'] }],
        },
        yaxis: {
            title: { text: 'Price', font: { size: 10 } },
            gridcolor: '#111111',
            linecolor: '#222222',
            tickfont: { size: 10 },
            side: 'left',
            range: [minPrice - priceRange * 0.25, maxPrice + priceRange * 0.05],
        },
        yaxis2: {
            title: { text: 'RSI', font: { size: 10 } },
            overlaying: 'y', side: 'right',
            range: [0, 100],
            showgrid: false,
            tickfont: { size: 9 },
            visible: activeIndicators.has('rsi'),
        },
        yaxis3: {
            overlaying: 'y', side: 'right',
            range: [0, maxVol * 5],
            showgrid: false,
            showticklabels: false,
            visible: activeIndicators.has('volume'),
        },
        yaxis4: {
            title: { text: 'MACD', font: { size: 9 } },
            overlaying: 'y', side: 'right',
            showgrid: false,
            tickfont: { size: 9 },
            visible: activeIndicators.has('macd'),
            position: 0.97,
        },
    };
}

// ─── Render ───────────────────────────────────────────────────────────────────

/**
 * Render (or update) the unified chart.
 * Caches data in state so indicator toggles can re-render without a new fetch.
 *
 * @param {Object} data - /api/stock-data response
 */
export function renderChart(data) {
    if (!data || !data.dates?.length) {
        updateStatus('No chart data to display.');
        return;
    }

    setLastChartData(data);
    const ticker = data.ticker || dom.tickerInput?.value?.trim() || '';

    const traces = [buildCandlestickTrace(data), ...buildIndicatorTraces(data)];
    const layout = buildChartLayout(data, ticker);

    Plotly.react(dom.chartDiv, traces, layout, {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
    });
}
