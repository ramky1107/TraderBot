// Stock Market Simulator - Frontend JavaScript

// Configuration
const API_URL = '/api/stock-data';
const AUTO_REFRESH_INTERVAL = 300000; // 5 minutes

// State
let currentTicker = '^NSEI';
let autoRefreshTimer = null;

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

    // Auto-refresh
    startAutoRefresh();
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

// Render Plotly chart
function renderChart(data) {
    const { dates, open, high, low, close, volume, sma_20, rsi, ticker } = data;

    // Create traces
    const traces = [];

    // Candlestick
    traces.push({
        type: 'candlestick',
        x: dates,
        open: open,
        high: high,
        low: low,
        close: close,
        name: 'OHLC',
        xaxis: 'x',
        yaxis: 'y'
    });

    // 20-Day MA
    if (sma_20 && sma_20.length > 0) {
        traces.push({
            type: 'scatter',
            x: dates,
            y: sma_20,
            mode: 'lines',
            name: '20-Day MA',
            line: { color: '#FF9800', width: 2 },
            xaxis: 'x',
            yaxis: 'y'
        });
    }

    // RSI
    if (rsi && rsi.length > 0) {
        traces.push({
            type: 'scatter',
            x: dates,
            y: rsi,
            mode: 'lines',
            name: 'RSI',
            line: { color: '#9C27B0', width: 2 },
            xaxis: 'x2',
            yaxis: 'y2'
        });
    }

    // Volume
    traces.push({
        type: 'bar',
        x: dates,
        y: volume,
        name: 'Volume',
        marker: { color: '#4FC3F7' },
        xaxis: 'x3',
        yaxis: 'y3'
    });

    // Layout
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
        xaxis: {
            domain: [0, 1],
            anchor: 'y',
            showgrid: true,
            gridcolor: '#2A2E39',
            rangebreaks: [{ bounds: ['sat', 'mon'] }]
        },
        yaxis: {
            domain: [0.5, 1],
            title: 'Price',
            titlefont: { size: 12 }
        },
        xaxis2: {
            domain: [0, 1],
            anchor: 'y2',
            showgrid: true,
            gridcolor: '#2A2E39',
            rangebreaks: [{ bounds: ['sat', 'mon'] }]
        },
        yaxis2: {
            domain: [0.25, 0.47],
            title: 'RSI',
            titlefont: { size: 12 },
            range: [0, 100]
        },
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

    // Add RSI reference lines
    const shapes = [
        {
            type: 'line',
            xref: 'paper',
            yref: 'y2',
            x0: 0,
            x1: 1,
            y0: 70,
            y1: 70,
            line: { color: '#EF5350', width: 1, dash: 'dash' },
            opacity: 0.5
        },
        {
            type: 'line',
            xref: 'paper',
            yref: 'y2',
            x0: 0,
            x1: 1,
            y0: 30,
            y1: 30,
            line: { color: '#26A69A', width: 1, dash: 'dash' },
            opacity: 0.5
        }
    ];

    layout.shapes = shapes;

    // Config
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
        restartAutoRefresh();
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

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
});
