/**
 * renderers.js — DOM render helpers for the sidebar.
 *
 * Exports:
 *   renderSentimentScore(data)
 *   renderConfidenceBadge(confidence)
 *   renderSignalActionBar(signals)
 *   renderNewsHeadlines(headlines)
 */

import * as dom from './dom.js';

// ─── Sentiment Score ──────────────────────────────────────────────────────────

/**
 * Update the sentiment score section.
 * @param {Object} data - /api/sentiment-score response
 */
export function renderSentimentScore(data) {
    const score = data.score ?? 0;
    const label = data.label || 'Neutral';

    if (dom.sentimentScoreValue) {
        dom.sentimentScoreValue.textContent = score;
        dom.sentimentScoreValue.className = 'sentiment-score-value ' + (
            score > 10 ? 'positive' : score < -10 ? 'negative' : 'neutral'
        );
    }

    if (dom.sentimentLabel) dom.sentimentLabel.textContent = label;

    // Needle: score -100..+100 → 0..100% left
    const needlePct = ((score + 100) / 200) * 100;
    if (dom.sentimentNeedle) dom.sentimentNeedle.style.left = `${needlePct}%`;

    // Score breakdown
    if (dom.techScore) dom.techScore.textContent = data.technical?.score ?? '--';
    if (dom.newsScore) dom.newsScore.textContent = data.news?.score ?? '--';
    if (dom.liveScore) dom.liveScore.textContent = data.live?.score ?? '--';
    if (dom.intrinsicValue) {
        const iv = data.intrinsic_value;
        dom.intrinsicValue.textContent = iv ? `₹${iv.toLocaleString()}` : '--';
    }

    renderConfidenceBadge(data.confidence ?? 0);
}

// ─── Confidence Badge ─────────────────────────────────────────────────────────

/**
 * Update the confidence badge colour and text.
 * @param {number} confidence - 0 to 100
 */
export function renderConfidenceBadge(confidence) {
    if (!dom.confidenceBadge || !dom.confidenceValue) return;

    dom.confidenceValue.textContent = `${confidence}%`;
    dom.confidenceBadge.className = 'confidence-badge ' + (
        confidence >= 70 ? 'high' : confidence >= 40 ? 'medium' : 'low'
    );
}

// ─── Signal Action Bar ────────────────────────────────────────────────────────

/**
 * Populate the signal chips in the bottom action bar.
 *
 * Chip colour rules:
 *   🟢 / 📈 → bullish   🔴 → bearish   ⚠️ → warning   else → neutral
 *
 * @param {string[]} signals
 */
export function renderSignalActionBar(signals) {
    if (!dom.signalChipsContainer) return;

    if (!signals?.length) {
        dom.signalChipsContainer.innerHTML =
            '<span class="signal-chip neutral">No signals detected</span>';
        return;
    }

    dom.signalChipsContainer.innerHTML = signals.map(sig => {
        const cls = sig.startsWith('🟢') || sig.startsWith('📈') ? 'bullish'
            : sig.startsWith('🔴') ? 'bearish'
                : sig.startsWith('⚠️') ? 'warning'
                    : 'neutral';
        return `<span class="signal-chip ${cls}">${sig}</span>`;
    }).join('');
}

// ─── News Headlines ───────────────────────────────────────────────────────────

/**
 * Render news headlines in the sidebar.
 * @param {Array<{title, publisher, sentiment, url}>} headlines
 */
export function renderNewsHeadlines(headlines) {
    if (!dom.newsList) return;

    if (!headlines?.length) {
        dom.newsList.innerHTML = '<div class="news-placeholder">No headlines available.</div>';
        return;
    }

    dom.newsList.innerHTML = headlines.map(h => {
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
