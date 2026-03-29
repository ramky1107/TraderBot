/**
 * =============================================================================
 * app.js — Stock Market Simulator Frontend
 * =============================================================================
 *
 * Naming conventions:
 *   on*     → DOM event handlers (e.g. onFetchButtonClick)
 *   fetch*  → Async functions that call the backend API
 *   render* → Functions that update the DOM
 *   build*  → Pure functions that return data structures (no DOM side-effects)
 *
 * Unified Chart:
 *   All indicators (SMA20, SMA50, RSI, MACD, Bollinger Bands, Volume) are
 *   overlaid on a SINGLE Plotly panel. RSI uses a secondary y-axis (right).
 *   Volume bars are scaled to 20% of the chart height via yaxis range tricks.
 *   The `activeIndicators` Set tracks which overlays are currently visible.
 *
 * =============================================================================
 */

'use strict';

// ─── API Base URL ─────────────────────────────────────────────────────────────
const API_URL = window.location.origin;

// ─── DOM References ───────────────────────────────────────────────────────────
const tickerInput = document.getElementById('tickerInput');
const periodSelect = document.getElementById('periodSelect');
const intervalSelect = document.getElementById('intervalSelect');
const fetchBtn = document.getElementById('fetchBtn');
const generateScoreBtn = document.getElementById('generateScoreBtn');
const statusText = document.getElementById('statusText');
const chartDiv = document.getElementById('chart');

// Sidebar elements
const sentimentScoreValue = document.getElementById('sentimentScoreValue');
const sentimentLabel = document.getElementById('sentimentLabel');
const sentimentNeedle = document.getElementById('sentimentNeedle');
const confidenceBadge = document.getElementById('confidenceBadge');
const confidenceValue = document.getElementById('confidenceValue');
const livePriceValue = document.getElementById('livePriceValue');
const livePriceChange = document.getElementById('livePriceChange');
const techScore = document.getElementById('techScore');
const newsScore = document.getElementById('newsScore');
const liveScore = document.getElementById('liveScore');
const newsList = document.getElementById('newsList');
const signalChipsContainer = document.getElementById('signalChipsContainer');

// Chatbot elements
const chatbotContainer = document.getElementById('chatbotContainer');
const chatbotMessages = document.getElementById('chatbotMessages');
const chatbotInput = document.getElementById('chatbotInput');
const chatbotSend = document.getElementById('chatbotSend');
const chatbotToggle = document.getElementById('chatbotToggle');
const chatbotClose = document.getElementById('chatbotClose');

// ─── Indicator Toggle State ───────────────────────────────────────────────────
/**
 * Set of currently active indicator overlays.
 * Keys must match `data-indicator` attributes in index.html
 * and the cases in buildIndicatorTraces().
 */
const activeIndicators = new Set(['sma20', 'volume']);

/** Last fetched chart data — stored so toggles can re-render without a new API call. */
let lastChartData = null;

// ─── WebSocket ────────────────────────────────────────────────────────────────
let socket = null;

// ─── Polling Intervals ────────────────────────────────────────────────────────
let livePriceInterval = null;

// =============================================================================
// STATUS HELPERS
// =============================================================================

/**
 * Update the status text in the toolbar.
 * @param {string} msg
 */
function updateStatus(msg) {
    if (statusText) statusText.textContent = msg;
}

// =============================================================================
// INDICATOR TOGGLE LOGIC
// =============================================================================

/**
 * Initialise indicator toggle buttons.
 * Each button with class `ind-toggle` toggles its `data-indicator` key
 * in `activeIndicators` and re-renders the chart.
 */
function initIndicatorToggles() {
    document.querySelectorAll('.ind-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.indicator;
            if (activeIndicators.has(key)) {
                activeIndicators.delete(key);
                btn.classList.remove('active');
            } else {
                activeIndicators.add(key);
                btn.classList.add('active');
            }
            // Re-render chart with current data and new indicator selection
            if (lastChartData) {
                renderChart(lastChartData);
            }
        });
    });
}

// =============================================================================
// CHART BUILDING
// =============================================================================

/**
 * Build the candlestick trace (always shown).
 * @param {Object} data - API response from /api/stock-data
 * @returns {Object} Plotly trace
 */
function buildCandlestickTrace(data) {
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

/**
 * Build all active indicator traces based on `activeIndicators`.
 * All price-scale indicators use yaxis:'y'.
 * RSI uses yaxis:'y2' (secondary right axis, 0–100).
 * Volume uses yaxis:'y3' (secondary right axis, scaled to 20% of chart).
 *
 * @param {Object} data - API response from /api/stock-data
 * @returns {Array<Object>} Array of Plotly traces
 */
function buildIndicatorTraces(data) {
    const traces = [];

    // ── SMA 20 ────────────────────────────────────────────────────────────────
    if (activeIndicators.has('sma20') && data.sma_20?.length) {
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.sma_20,
            name: 'SMA 20',
            yaxis: 'y',
            line: { color: '#f39c12', width: 1.5, dash: 'solid' },
        });
    }

    // ── SMA 50 ────────────────────────────────────────────────────────────────
    if (activeIndicators.has('sma50') && data.sma_50?.length) {
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.sma_50,
            name: 'SMA 50',
            yaxis: 'y',
            line: { color: '#9b59b6', width: 1.5, dash: 'solid' },
        });
    }

    // ── Bollinger Bands ───────────────────────────────────────────────────────
    if (activeIndicators.has('bb') && data.bb_upper?.length) {
        // Upper band
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.bb_upper,
            name: 'BB Upper',
            yaxis: 'y',
            line: { color: 'rgba(52, 152, 219, 0.6)', width: 1, dash: 'dot' },
            showlegend: true,
        });
        // Lower band — fill to upper to create the band area
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.bb_lower,
            name: 'BB Lower',
            yaxis: 'y',
            line: { color: 'rgba(52, 152, 219, 0.6)', width: 1, dash: 'dot' },
            fill: 'tonexty',
            fillcolor: 'rgba(52, 152, 219, 0.05)',
            showlegend: false,
        });
        // Middle band (SMA20)
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.bb_middle,
            name: 'BB Mid',
            yaxis: 'y',
            line: { color: 'rgba(52, 152, 219, 0.4)', width: 1 },
            showlegend: false,
        });
    }

    // ── RSI (secondary right y-axis, 0–100) ──────────────────────────────────
    if (activeIndicators.has('rsi') && data.rsi?.length) {
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.rsi,
            name: 'RSI (14)',
            yaxis: 'y2',
            line: { color: '#e74c3c', width: 1.5 },
        });
        // Overbought reference line at 70
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: [data.dates[0], data.dates[data.dates.length - 1]],
            y: [70, 70],
            name: 'RSI 70',
            yaxis: 'y2',
            line: { color: 'rgba(231, 76, 60, 0.3)', width: 1, dash: 'dash' },
            showlegend: false,
        });
        // Oversold reference line at 30
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: [data.dates[0], data.dates[data.dates.length - 1]],
            y: [30, 30],
            name: 'RSI 30',
            yaxis: 'y2',
            line: { color: 'rgba(39, 174, 96, 0.3)', width: 1, dash: 'dash' },
            showlegend: false,
        });
    }

    // ── MACD (overlaid on price panel, normalised) ────────────────────────────
    if (activeIndicators.has('macd') && data.macd?.length) {
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.macd,
            name: 'MACD',
            yaxis: 'y4',
            line: { color: '#1abc9c', width: 1.5 },
        });
        traces.push({
            type: 'scatter',
            mode: 'lines',
            x: data.dates,
            y: data.macd_signal,
            name: 'MACD Signal',
            yaxis: 'y4',
            line: { color: '#e67e22', width: 1, dash: 'dot' },
        });
    }

    // ── Volume (scaled to 20% of chart via y3 range) ──────────────────────────
    if (activeIndicators.has('volume') && data.volume?.length) {
        const maxVol = Math.max(...data.volume.filter(v => v != null));
        traces.push({
            type: 'bar',
            x: data.dates,
            y: data.volume,
            name: 'Volume',
            yaxis: 'y3',
            marker: { color: 'rgba(100, 149, 237, 0.35)' },
            // Volume bars sit at the very bottom of the chart
        });
        // Store maxVol on the trace for layout use
        traces[traces.length - 1]._maxVol = maxVol;
    }

    return traces;
}

/**
 * Build the Plotly layout for the unified single-panel chart.
 * Uses multiple y-axes overlaid on the same x-axis:
 *   y  → price (left axis, main)
 *   y2 → RSI 0–100 (right axis, overlaid)
 *   y3 → Volume (right axis, scaled to bottom 20%)
 *   y4 → MACD (right axis, overlaid, small range)
 *
 * @param {Object} data  - API response
 * @param {string} ticker
 * @returns {Object} Plotly layout
 */
function buildChartLayout(data, ticker) {
    const lastClose = data.close?.length ? data.close[data.close.length - 1] : 0;

    // Volume max for scaling y3 so bars occupy bottom 20%
    const maxVol = data.volume?.length
        ? Math.max(...data.volume.filter(v => v != null))
        : 1;

    // Price range for y axis
    const prices = [...(data.high || []), ...(data.low || [])].filter(v => v != null);
    const minPrice = prices.length ? Math.min(...prices) : 0;
    const maxPrice = prices.length ? Math.max(...prices) : 1;
    const priceRange = maxPrice - minPrice;

    return {
        // ── Title ─────────────────────────────────────────────────────────────
        title: {
            text: `${ticker} — Last: ${lastClose?.toFixed ? lastClose.toFixed(2) : lastClose}`,
            font: { size: 14, family: 'Inter, Ubuntu, sans-serif', color: '#D1D4DC' },
            x: 0.01,
            xanchor: 'left',
        },

        // ── Theme ─────────────────────────────────────────────────────────────
        paper_bgcolor: '#000000',
        plot_bgcolor: '#000000',
        font: { family: 'Inter, Ubuntu, sans-serif', color: '#D1D4DC', size: 11 },

        // ── Margins ───────────────────────────────────────────────────────────
        margin: { l: 60, r: 80, t: 40, b: 40 },
        height: null,   // Let CSS control height

        // ── Hover ─────────────────────────────────────────────────────────────
        hovermode: 'x unified',
        hoverlabel: { bgcolor: '#1a1a2e', font: { color: '#D1D4DC' } },

        // ── Legend ────────────────────────────────────────────────────────────
        legend: {
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.01,
            xanchor: 'right',
            x: 1,
            font: { size: 10 },
            bgcolor: 'rgba(0,0,0,0)',
        },

        // ── X Axis ────────────────────────────────────────────────────────────
        xaxis: {
            rangeslider: { visible: false },
            gridcolor: '#111111',
            linecolor: '#222222',
            tickfont: { size: 10 },
            rangebreaks: [{ bounds: ['sat', 'mon'] }],
        },

        // ── Y Axis: Price (left) ──────────────────────────────────────────────
        yaxis: {
            title: { text: 'Price', font: { size: 10 } },
            gridcolor: '#111111',
            linecolor: '#222222',
            tickfont: { size: 10 },
            side: 'left',
            // Extend range downward so volume bars don't overlap candles
            range: [minPrice - priceRange * 0.25, maxPrice + priceRange * 0.05],
        },

        // ── Y Axis 2: RSI (right, 0–100) ──────────────────────────────────────
        yaxis2: {
            title: { text: 'RSI', font: { size: 10 } },
            overlaying: 'y',
            side: 'right',
            range: [0, 100],
            gridcolor: 'rgba(0,0,0,0)',   // No grid for secondary axes
            tickfont: { size: 9 },
            showgrid: false,
            visible: activeIndicators.has('rsi'),
        },

        // ── Y Axis 3: Volume (right, scaled to bottom 20%) ────────────────────
        yaxis3: {
            overlaying: 'y',
            side: 'right',
            // Set range so max volume = 20% of chart height
            range: [0, maxVol * 5],
            showgrid: false,
            showticklabels: false,
            visible: activeIndicators.has('volume'),
        },

        // ── Y Axis 4: MACD (right, small range) ───────────────────────────────
        yaxis4: {
            title: { text: 'MACD', font: { size: 9 } },
            overlaying: 'y',
            side: 'right',
            showgrid: false,
            tickfont: { size: 9 },
            visible: activeIndicators.has('macd'),
            // Offset so it doesn't collide with RSI axis
            position: 0.97,
        },
    };
}

/**
 * Render the unified chart with all active indicator overlays.
 * Stores `data` in `lastChartData` so indicator toggles can re-render
 * without a new API call.
 *
 * @param {Object} data - API response from /api/stock-data
 */
function renderChart(data) {
    if (!data || !data.dates?.length) {
        updateStatus('No chart data to display.');
        return;
    }

    lastChartData = data;
    const ticker = data.ticker || tickerInput.value.trim();

    const traces = [
        buildCandlestickTrace(data),
        ...buildIndicatorTraces(data),
    ];
    const layout = buildChartLayout(data, ticker);

    Plotly.react(chartDiv, traces, layout, {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
    });
}

// =============================================================================
// DATA FETCHING
// =============================================================================

/**
 * Fetch OHLCV + indicator data from /api/stock-data and render the chart.
 * @param {string} ticker
 */
async function fetchStockData(ticker) {
    const period = periodSelect?.value || '5d';
    const interval = intervalSelect?.value || '1d';

    try {
        updateStatus(`Fetching ${ticker} (${period}/${interval})...`);
        fetchBtn.classList.add('loading');

        const res = await fetch(`${API_URL}/api/stock-data?ticker=${encodeURIComponent(ticker)}&period=${period}&interval=${interval}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            updateStatus(`Error: ${data.error || res.statusText}`);
            return;
        }

        renderChart(data);
        updateStatus(`${ticker} loaded — ${data.dates?.length || 0} bars`);

    } catch (err) {
        console.error('[fetchStockData]', err);
        updateStatus(`Error: ${err.message}`);
    } finally {
        fetchBtn.classList.remove('loading');
    }
}

/**
 * Fetch and display the live price for a ticker.
 * @param {string} ticker
 */
async function fetchLivePrice(ticker) {
    try {
        const res = await fetch(`${API_URL}/api/live-price?ticker=${encodeURIComponent(ticker)}`);
        const data = await res.json();

        if (!res.ok || data.error) return;

        livePriceValue.textContent = `₹${data.current_price?.toLocaleString('en-IN') || '--'}`;
        const pct = data.change_pct ?? 0;
        const sign = pct >= 0 ? '+' : '';
        const cls = pct >= 0 ? 'positive' : 'negative';
        livePriceChange.textContent = `${sign}${pct.toFixed(2)}%`;
        livePriceChange.className = `live-price-change ${cls}`;

    } catch (err) {
        console.error('[fetchLivePrice]', err);
    }
}

/**
 * Fetch the full sentiment analysis from /api/sentiment-score and update
 * the sidebar (score, label, confidence, breakdown, signals).
 * @param {string} ticker
 */
async function fetchSentimentScore(ticker) {
    try {
        updateStatus(`Analyzing ${ticker}...`);
        generateScoreBtn.classList.add('loading');

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
        console.error('[fetchSentimentScore]', err);
        updateStatus(`Error: ${err.message}`);
    } finally {
        generateScoreBtn.classList.remove('loading');
    }
}

/**
 * Fetch financial ratios from /api/financial-ratios and update the sidebar.
 * @param {string} ticker
 */
async function fetchFinancialRatios(ticker) {
    try {
        const res = await fetch(`${API_URL}/api/financial-ratios?ticker=${encodeURIComponent(ticker)}`);
        const data = await res.json();

        if (!res.ok || data.error) return;

        const r = data.ratios || {};
        document.getElementById('peRatio').textContent = r.pe_ratio || '--';
        document.getElementById('pbRatio').textContent = r.pb_ratio || '--';
        document.getElementById('debtEquity').textContent = r.debt_equity || '--';
        document.getElementById('marketCap').textContent = r.market_cap || '--';
        document.getElementById('dividendYield').textContent = r.dividend_yield || '--';
        document.getElementById('roeValue').textContent = r.roe || '--';
        document.getElementById('epsValue').textContent = r.eps || '--';
        document.getElementById('bookValue').textContent = r.book_value || '--';

    } catch (err) {
        console.error('[fetchFinancialRatios]', err);
    }
}

// =============================================================================
// RENDER HELPERS
// =============================================================================

/**
 * Update the sentiment score section in the sidebar.
 * @param {Object} data - Sentiment API response
 */
function renderSentimentScore(data) {
    const score = data.score ?? 0;
    const label = data.label || 'Neutral';

    sentimentScoreValue.textContent = score;
    sentimentLabel.textContent = label;

    // Colour the score value
    sentimentScoreValue.className = 'sentiment-score-value ' + (
        score > 10 ? 'positive' : score < -10 ? 'negative' : 'neutral'
    );

    // Move the needle: score -100..+100 → 0..100% left
    const needlePct = ((score + 100) / 200) * 100;
    if (sentimentNeedle) sentimentNeedle.style.left = `${needlePct}%`;

    // Score breakdown
    if (techScore) techScore.textContent = data.technical?.score ?? '--';
    if (newsScore) newsScore.textContent = data.news?.score ?? '--';
    if (liveScore) liveScore.textContent = data.live?.score ?? '--';

    // Confidence badge
    renderConfidenceBadge(data.confidence ?? 0);
}

/**
 * Update the confidence badge colour and text.
 * @param {number} confidence - 0 to 100
 */
function renderConfidenceBadge(confidence) {
    if (!confidenceBadge || !confidenceValue) return;
    confidenceValue.textContent = `${confidence}%`;
    confidenceBadge.className = 'confidence-badge ' + (
        confidence >= 70 ? 'high' : confidence >= 40 ? 'medium' : 'low'
    );
}

/**
 * Populate the signal action bar at the bottom of the screen.
 * Each signal string gets a colour-coded chip.
 *
 * Signal prefixes → chip class:
 *   🟢 → bullish (green)
 *   🔴 → bearish (red)
 *   ⚠️ → warning (amber)
 *   📈 → bullish
 *   anything else → neutral (grey)
 *
 * @param {string[]} signals
 */
function renderSignalActionBar(signals) {
    if (!signalChipsContainer) return;

    if (!signals || signals.length === 0) {
        signalChipsContainer.innerHTML =
            '<span class="signal-chip neutral">No signals detected</span>';
        return;
    }

    signalChipsContainer.innerHTML = signals.map(sig => {
        const cls = sig.startsWith('🟢') || sig.startsWith('📈') ? 'bullish'
            : sig.startsWith('🔴') ? 'bearish'
                : sig.startsWith('⚠️') ? 'warning'
                    : 'neutral';
        return `<span class="signal-chip ${cls}">${sig}</span>`;
    }).join('');
}

/**
 * Render news headlines in the sidebar.
 * Each headline gets a coloured dot (green/red/grey) based on sentiment.
 *
 * @param {Array<{title, publisher, sentiment, url}>} headlines
 */
function renderNewsHeadlines(headlines) {
    if (!newsList) return;

    if (!headlines || headlines.length === 0) {
        newsList.innerHTML = '<div class="news-placeholder">No headlines available.</div>';
        return;
    }

    newsList.innerHTML = headlines.map(h => {
        const dotCls = h.sentiment === 'positive' ? 'positive'
            : h.sentiment === 'negative' ? 'negative'
                : 'neutral';
        const url = h.url || '#';
        return `
            <div class="news-item">
                <span class="news-dot ${dotCls}"></span>
                <div class="news-item-content">
                    <a class="news-item-title" href="${url}" target="_blank" rel="noopener">
                        ${h.title || 'No title'}
                    </a>
                    <span class="news-item-publisher">${h.publisher || ''}</span>
                </div>
            </div>`;
    }).join('');
}

// =============================================================================
// WEBSOCKET
// =============================================================================

/**
 * Initialise the Socket.IO connection (lazy — only called once).
 * Listens for 'new_news' events and updates the news sidebar.
 * @param {string} ticker
 */
function initWebSocket(ticker) {
    if (socket) {
        socket.emit('activate_news', { ticker });
        return;
    }

    socket = io(API_URL);

    socket.on('connect', () => {
        console.log('[WS] Connected');
        socket.emit('activate_news', { ticker });
    });

    socket.on('new_news', data => {
        const headlines = data?.headlines || [];
        if (headlines.length > 0) {
            renderNewsHeadlines(headlines);
        }
    });

    socket.on('disconnect', () => console.log('[WS] Disconnected'));
}

// =============================================================================
// CHATBOT
// =============================================================================

/**
 * Append a message bubble to the chatbot panel.
 * @param {string} text
 * @param {'user'|'bot'} sender
 */
function appendChatMessage(text, sender) {
    const div = document.createElement('div');
    div.className = `chatbot-message ${sender}-message`;
    div.textContent = text;
    chatbotMessages.appendChild(div);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

/**
 * Send the user's message to /api/chatbot and display the response.
 */
async function onChatbotSend() {
    const msg = chatbotInput.value.trim();
    if (!msg) return;

    appendChatMessage(msg, 'user');
    chatbotInput.value = '';

    try {
        const res = await fetch(`${API_URL}/api/chatbot`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        });
        const data = await res.json();
        appendChatMessage(data.response || data.error || 'No response.', 'bot');
    } catch (err) {
        appendChatMessage(`Error: ${err.message}`, 'bot');
    }
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

/** Handle "Update Chart" button click. */
function onFetchButtonClick() {
    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) return;
    tickerInput.value = ticker;

    // Clear any existing live price polling
    if (livePriceInterval) clearInterval(livePriceInterval);

    fetchStockData(ticker);
    fetchLivePrice(ticker);

    // Poll live price every 30 seconds
    livePriceInterval = setInterval(() => fetchLivePrice(ticker), 30_000);
}

/** Handle "Generate Score" button click. */
function onGenerateScoreClick() {
    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) return;

    fetchSentimentScore(ticker);
    fetchFinancialRatios(ticker);
    initWebSocket(ticker);
}

/** Handle Enter key in the ticker input. */
function onTickerInputKeydown(e) {
    if (e.key === 'Enter') onFetchButtonClick();
}

/** Handle Enter key in the chatbot input. */
function onChatbotInputKeydown(e) {
    if (e.key === 'Enter') onChatbotSend();
}

// =============================================================================
// INITIALISATION
// =============================================================================

/**
 * Wire up all event listeners and load the default chart on page load.
 */
function init() {
    // Toolbar
    fetchBtn?.addEventListener('click', onFetchButtonClick);
    generateScoreBtn?.addEventListener('click', onGenerateScoreClick);
    tickerInput?.addEventListener('keydown', onTickerInputKeydown);

    // Period / interval selects trigger a chart refresh
    periodSelect?.addEventListener('change', onFetchButtonClick);
    intervalSelect?.addEventListener('change', onFetchButtonClick);

    // Indicator toggles
    initIndicatorToggles();

    // Chatbot
    chatbotSend?.addEventListener('click', onChatbotSend);
    chatbotInput?.addEventListener('keydown', onChatbotInputKeydown);
    chatbotToggle?.addEventListener('click', () => {
        chatbotContainer.classList.toggle('open');
    });
    chatbotClose?.addEventListener('click', () => {
        chatbotContainer.classList.remove('open');
    });

    // Load default chart on startup
    const defaultTicker = tickerInput?.value?.trim() || '^NSEI';
    fetchStockData(defaultTicker);
    fetchLivePrice(defaultTicker);
    livePriceInterval = setInterval(() => fetchLivePrice(defaultTicker), 30_000);
}

// Run after DOM is ready
document.addEventListener('DOMContentLoaded', init);
