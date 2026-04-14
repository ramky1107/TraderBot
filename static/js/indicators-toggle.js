/**
 * indicators-toggle.js — Indicator overlay toggle button logic.
 *
 * Wires click handlers to all `.ind-toggle` buttons.
 * Toggling a button adds/removes its key from `activeIndicators`
 * and re-renders the chart without a new API call.
 */

import { activeIndicators, getLastChartData } from './state.js';
import { renderChart } from './chart.js';

/**
 * Attach click listeners to every `.ind-toggle` button.
 * Safe to call multiple times — uses replaceWith to avoid duplicate listeners.
 */
export function initIndicatorToggles() {
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

            const cached = getLastChartData();
            if (cached) renderChart(cached);
        });
    });
}
