// Stock Market Simulator - Frontend JavaScript

// Configuration
const API_URL = '/api/stock-data';
const SENTIMENT_API_URL = '/api/sentiment-score';
const LIVE_PRICE_API_URL = '/api/live-price';
const AUTO_REFRESH_INTERVAL = 300000; // 5 minutes
const LIVE_PRICE_INTERVAL = 60000;    // 1 minute
const SENTIMENT_REFRESH_INTERVAL = 300000; // 5 minutes

// State
let currentTicker = '^NSEI';
let autoRefreshTimer = null;
let livePriceTimer = null;
let sentimentTimer = null;

// DOM Elements
const tickerInput = document.getElementById('tickerInput');
const fetchBtn = document.getElementById('fetchBtn');
const statusText = document.getElementById('statusText');
const chartDiv = document.getElementById('chart');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchBtn.addEventListener('click', handleFetchClick);
    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleFetchClick();
    });

    // Initial load
    fetchStockData(currentTicker);
    fetchSentimentScore(currentTicker);
    fetchLivePrice(currentTicker);

    // Auto-refresh
    startAutoRefresh();
    startLivePricePolling();
    startSentimentRefresh();
});

// Fetch stock data from API
async function fetchStockData(ticker) {
    try {
        updateStatus('Loading...');
        fetchBtn.classList.add('loading');

        const response = await fetch(`${API_URL}?ticker=${encodeURIComponent(ticker)}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        renderChart(data);
        currentTicker = ticker;
        updateStatus('Ready');

    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus('Error: ' + error.message);
    } finally {
        fetchBtn.classList.remove('loading');
    }
}

// Render Plotly chart — RSI on top, Price in middle, Volume at bottom
function renderChart(data) {
    const { dates, open, high, low, close, volume, sma_20, rsi, ticker } = data;

    const traces = [];

    // --- RSI (top panel, y/x axes) ---
    if (rsi && rsi.length > 0) {
        const validRsiData = [];
        const validRsiDates = [];
        for (let i = 0; i < rsi.length; i++) {
            const val = rsi[i];
            if (val !== null && !isNaN(val) && val > 0 && val < 100) {
                validRsiData.push(val);
                validRsiDates.push(dates[i]);
            }
        }
        if (validRsiData.length >= 1) {
            traces.push({
                type: 'scatter',
                x: validRsiDates,
                y: validRsiData,
                mode: 'lines',
                name: 'RSI',
                line: { color: '#9C27B0', width: 2 },
                xaxis: 'x',
                yaxis: 'y',
                connectgaps: false
            });
        }
    }

    // --- Candlestick (middle panel, y2/x2 axes) ---
    traces.push({
        type: 'candlestick',
        x: dates,
        open: open,
        high: high,
        low: low,
        close: close,
        name: 'OHLC',
        xaxis: 'x2',
        yaxis: 'y2',
        increasing: { line: { color: '#26A69A' } },
        decreasing: { line: { color: '#EF5350' } }
    });

    // 20-Day Moving Average (middle panel, same y2/x2)
    if (sma_20 && sma_20.length > 0) {
        const validSmaData = [];
        const validSmaDates = [];
        for (let i = 0; i < sma_20.length; i++) {
            const val = sma_20[i];
            if (val !== null && !isNaN(val) && val > 0) {
                validSmaData.push(val);
                validSmaDates.push(dates[i]);
            }
        }
        if (validSmaData.length >= 1) {
            traces.push({
                type: 'scatter',
                x: validSmaDates,
                y: validSmaData,
                mode: 'lines',
                name: '20-Day MA',
                line: { color: '#FF9800', width: 2 },
                xaxis: 'x2',
                yaxis: 'y2',
                connectgaps: false
            });
        }
    }

    // --- Volume (bottom panel, y3/x3 axes) ---
    traces.push({
        type: 'bar',
        x: dates,
        y: volume,
        name: 'Volume',
        marker: { color: '#4FC3F7' },
        xaxis: 'x3',
        yaxis: 'y3'
    });

    // Layout: RSI top, Price middle, Volume bottom
    const layout = {
        title: {
            text: `${ticker} - Last: ${close[close.length - 1]?.toFixed(2) || 'N/A'}`,
            font: { size: 16, family: 'Ubuntu, sans-serif', color: '#D1D4DC' },
            x: 0.01,
            xanchor: 'left'
        },
        grid: {
            rows: 3,
            columns: 1,
            pattern: 'independent',
            roworder: 'top to bottom'
        },
        // RSI (top)
        xaxis: {
            domain: [0, 1],
            anchor: 'y',
            showgrid: true,
            gridcolor: '#2A2E39',
            rangebreaks: [{ bounds: ['sat', 'mon'] }]
        },
        yaxis: {
            domain: [0.82, 1],
            title: 'RSI',
            titlefont: { size: 12 },
            range: [0, 100]
        },
        // Price (middle)
        xaxis2: {
            domain: [0, 1],
            anchor: 'y2',
            showgrid: true,
            gridcolor: '#2A2E39',
            rangebreaks: [{ bounds: ['sat', 'mon'] }]
        },
        yaxis2: {
            domain: [0.25, 0.79],
            title: 'Price',
            titlefont: { size: 12 }
        },
        // Volume (bottom)
        xaxis3: {
            domain: [0, 1],
            anchor: 'y3',
            showgrid: true,
            gridcolor: '#2A2E39',
            rangebreaks: [{ bounds: ['sat', 'mon'] }]
        },
        yaxis3: {
            domain: [0, 0.22],
            title: 'Volume',
            titlefont: { size: 12 }
        },
        paper_bgcolor: '#131722',
        plot_bgcolor: '#131722',
        font: { family: 'Ubuntu, sans-serif', color: '#D1D4DC', size: 12 },
        showlegend: true,
        legend: {
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.01,
            xanchor: 'right',
            x: 1,
            font: { size: 11 }
        },
        margin: { l: 60, r: 20, t: 50, b: 40 },
        hovermode: 'x unified',
        xaxis_rangeslider_visible: false
    };

    // RSI reference lines (on y axis, which is now the top panel)
    const shapes = [
        {
            type: 'line',
            xref: 'paper',
            yref: 'y',
            x0: 0, x1: 1,
            y0: 70, y1: 70,
            line: { color: '#EF5350', width: 1, dash: 'dash' },
            opacity: 0.5
        },
        {
            type: 'line',
            xref: 'paper',
            yref: 'y',
            x0: 0, x1: 1,
            y0: 30, y1: 30,
            line: { color: '#26A69A', width: 1, dash: 'dash' },
            opacity: 0.5
        }
    ];

    layout.shapes = shapes;

    const config = {
        displayModeBar: false,
        responsive: true
    };

    // Render
    Plotly.newPlot(chartDiv, traces, layout, config);
}

// Handle fetch button click
function handleFetchClick() {
    const ticker = tickerInput.value.trim();
    if (ticker) {
        fetchStockData(ticker);
        fetchSentimentScore(ticker);
        fetchLivePrice(ticker);
        currentTicker = ticker;
        restartAutoRefresh();
        restartLivePricePolling();
        restartSentimentRefresh();
    }
}

// Update status text
function updateStatus(message) {
    statusText.textContent = message;
}

// Auto-refresh functionality
function startAutoRefresh() {
    autoRefreshTimer = setInterval(() => {
        fetchStockData(currentTicker);
    }, AUTO_REFRESH_INTERVAL);
}

function restartAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
    startAutoRefresh();
}

// ===== SENTIMENT SCORE FUNCTIONS =====

// Fetch sentiment score from API
async function fetchSentimentScore(ticker) {
    const scoreEl = document.getElementById('sentimentScoreValue');
    const labelEl = document.getElementById('sentimentLabel');

    try {
        // Show loading state
        scoreEl.className = 'sentiment-score-value loading';
        scoreEl.textContent = '...';
        labelEl.textContent = 'Analyzing...';

        const response = await fetch(`${SENTIMENT_API_URL}?ticker=${encodeURIComponent(ticker)}`);
        const data = await response.json();

        if (data.error) {
            scoreEl.className = 'sentiment-score-value';
            scoreEl.textContent = '--';
            labelEl.textContent = 'Error';
            return;
        }

        // Update main score
        updateSentimentDisplay(data);

    } catch (error) {
        console.error('Sentiment fetch error:', error);
        scoreEl.className = 'sentiment-score-value';
        scoreEl.textContent = '--';
        labelEl.textContent = 'Unavailable';
    }
}

// Update all sentiment UI elements
function updateSentimentDisplay(data) {
    const score = data.score;
    const label = data.label;

    // Determine color class
    let colorClass = 'neutral';
    if (score > 10) colorClass = 'bullish';
    else if (score < -10) colorClass = 'bearish';

    // Update score value (big font)
    const scoreEl = document.getElementById('sentimentScoreValue');
    scoreEl.textContent = (score > 0 ? '+' : '') + score;
    scoreEl.className = `sentiment-score-value ${colorClass}`;

    // Update label
    const labelEl = document.getElementById('sentimentLabel');
    labelEl.textContent = label;
    labelEl.className = `sentiment-score-label ${colorClass}`;

    // Update meter needle position (map -100..+100 to 0%..100%)
    const needlePos = ((score + 100) / 200) * 100;
    const needleEl = document.getElementById('sentimentNeedle');
    needleEl.style.left = `${needlePos}%`;

    // Update breakdown scores
    updateBreakdownScore('techScore', data.technical?.score);
    updateBreakdownScore('newsScore', data.news?.score);
    updateBreakdownScore('liveScore', data.live?.score);

    // Update news headlines
    renderNewsHeadlines(data.news?.headlines || []);
}

// Render news headlines in sidebar
function renderNewsHeadlines(headlines) {
    const newsList = document.getElementById('newsList');
    if (!newsList) return;

    if (!headlines || headlines.length === 0) {
        newsList.innerHTML = '<div class="news-placeholder">No recent news</div>';
        return;
    }

    newsList.innerHTML = headlines.map(item => {
        const sentimentClass = item.sentiment || 'neutral';
        const publisher = item.publisher ? `<div class="news-item-publisher">${item.publisher}</div>` : '';
        return `
            <div class="news-item ${sentimentClass}">
                <div class="news-item-title">${item.title || 'Untitled'}</div>
                ${publisher}
            </div>
        `;
    }).join('');
}

// Update individual breakdown score element
function updateBreakdownScore(elementId, value) {
    const el = document.getElementById(elementId);
    if (!el) return;

    if (value === undefined || value === null) {
        el.textContent = '--';
        el.className = 'breakdown-value';
        return;
    }

    el.textContent = (value > 0 ? '+' : '') + value;
    if (value > 0) {
        el.className = 'breakdown-value positive';
    } else if (value < 0) {
        el.className = 'breakdown-value negative';
    } else {
        el.className = 'breakdown-value neutral-val';
    }
}

// Fetch live price
async function fetchLivePrice(ticker) {
    try {
        const response = await fetch(`${LIVE_PRICE_API_URL}?ticker=${encodeURIComponent(ticker)}`);
        const data = await response.json();

        if (data.error) return;

        // Update live price display
        const priceEl = document.getElementById('livePriceValue');
        const changeEl = document.getElementById('livePriceChange');

        priceEl.textContent = data.current_price?.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }) || '--';

        if (data.change !== undefined) {
            const sign = data.change >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${data.change.toFixed(2)} (${sign}${data.change_pct.toFixed(2)}%)`;
            changeEl.className = `live-price-change ${data.change >= 0 ? 'positive' : 'negative'}`;
        }

    } catch (error) {
        console.error('Live price fetch error:', error);
    }
}

// Live price polling
function startLivePricePolling() {
    livePriceTimer = setInterval(() => {
        fetchLivePrice(currentTicker);
    }, LIVE_PRICE_INTERVAL);
}

function restartLivePricePolling() {
    if (livePriceTimer) clearInterval(livePriceTimer);
    startLivePricePolling();
}

// Sentiment refresh
function startSentimentRefresh() {
    sentimentTimer = setInterval(() => {
        fetchSentimentScore(currentTicker);
    }, SENTIMENT_REFRESH_INTERVAL);
}

function restartSentimentRefresh() {
    if (sentimentTimer) clearInterval(sentimentTimer);
    startSentimentRefresh();
}

// ===== CHATBOT FUNCTIONALITY =====

// Chatbot DOM Elements
const chatbotToggle = document.getElementById('chatbotToggle');
const chatbotContainer = document.getElementById('chatbotContainer');
const chatbotClose = document.getElementById('chatbotClose');
const chatbotInput = document.getElementById('chatbotInput');
const chatbotSend = document.getElementById('chatbotSend');
const chatbotMessages = document.getElementById('chatbotMessages');

// Chatbot State
let isChatbotOpen = false;

// Initialize chatbot event listeners
document.addEventListener('DOMContentLoaded', () => {
    chatbotToggle.addEventListener('click', toggleChatbot);
    chatbotClose.addEventListener('click', toggleChatbot);
    chatbotSend.addEventListener('click', sendMessage);
    chatbotInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// Toggle chatbot visibility
function toggleChatbot() {
    isChatbotOpen = !isChatbotOpen;
    chatbotContainer.classList.toggle('active', isChatbotOpen);

    if (isChatbotOpen) {
        chatbotInput.focus();
    }
}

// Send message to chatbot
async function sendMessage() {
    const message = chatbotInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    chatbotInput.value = '';

    // Disable input while processing
    chatbotSend.disabled = true;
    chatbotInput.disabled = true;

    // Show typing indicator
    const typingIndicator = addTypingIndicator();

    try {
        const response = await fetch('/api/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Remove typing indicator
        typingIndicator.remove();

        if (data.error) {
            addMessage(`Error: ${data.error}`, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }

    } catch (error) {
        typingIndicator.remove();
        addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        console.error('Chatbot error:', error);
    } finally {
        // Re-enable input
        chatbotSend.disabled = false;
        chatbotInput.disabled = false;
        chatbotInput.focus();
    }
}

// Add message to chat window
function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chatbot-message ${type}-message`;
    messageDiv.textContent = text;

    chatbotMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

    return messageDiv;
}

// Add typing indicator
function addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chatbot-message bot-message typing-indicator';
    typingDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;

    chatbotMessages.appendChild(typingDiv);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

    return typingDiv;
}
