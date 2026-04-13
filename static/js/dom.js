/**
 * dom.js — Cached DOM element references.
 *
 * Call populate() once after all HTML partials have been injected into
 * the document. Every other module imports named refs from here.
 */

// ── Toolbar ───────────────────────────────────────────────────────────────────
export let tickerInput = null;
export let periodSelect = null;
export let intervalSelect = null;
export let fetchBtn = null;
export let generateScoreBtn = null;
export let statusText = null;

// ── Chart ─────────────────────────────────────────────────────────────────────
export let chartDiv = null;

// ── Sidebar ───────────────────────────────────────────────────────────────────
export let sentimentScoreValue = null;
export let sentimentLabel = null;
export let sentimentNeedle = null;
export let confidenceBadge = null;
export let confidenceValue = null;
export let livePriceValue = null;
export let livePriceChange = null;
export let techScore = null;
export let newsScore = null;
export let liveScore = null;
export let intrinsicValue = null;
export let newsList = null;

// ── Signal bar ────────────────────────────────────────────────────────────────
export let signalChipsContainer = null;

// ── Chatbot ───────────────────────────────────────────────────────────────────
export let chatbotContainer = null;
export let chatbotMessages = null;
export let chatbotInput = null;
export let chatbotSend = null;
export let chatbotToggle = null;
export let chatbotClose = null;

/**
 * Resolve all DOM references.
 * Must be called after all partials have been injected.
 */
export function populate() {
    tickerInput = document.getElementById('tickerInput');
    periodSelect = document.getElementById('periodSelect');
    intervalSelect = document.getElementById('intervalSelect');
    fetchBtn = document.getElementById('fetchBtn');
    generateScoreBtn = document.getElementById('generateScoreBtn');
    statusText = document.getElementById('statusText');

    chartDiv = document.getElementById('chart');

    sentimentScoreValue = document.getElementById('sentimentScoreValue');
    sentimentLabel = document.getElementById('sentimentLabel');
    sentimentNeedle = document.getElementById('sentimentNeedle');
    confidenceBadge = document.getElementById('confidenceBadge');
    confidenceValue = document.getElementById('confidenceValue');
    livePriceValue = document.getElementById('livePriceValue');
    livePriceChange = document.getElementById('livePriceChange');
    techScore = document.getElementById('techScore');
    newsScore = document.getElementById('newsScore');
    liveScore = document.getElementById('liveScore');
    intrinsicValue = document.getElementById('intrinsicValue');
    newsList = document.getElementById('newsList');

    signalChipsContainer = document.getElementById('signalChipsContainer');

    chatbotContainer = document.getElementById('chatbotContainer');
    chatbotMessages = document.getElementById('chatbotMessages');
    chatbotInput = document.getElementById('chatbotInput');
    chatbotSend = document.getElementById('chatbotSend');
    chatbotToggle = document.getElementById('chatbotToggle');
    chatbotClose = document.getElementById('chatbotClose');
}
