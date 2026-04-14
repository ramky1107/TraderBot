/**
 * status.js — Status bar helper.
 * Thin wrapper so every module can update the toolbar status text
 * without importing the full dom module.
 */

import * as dom from './dom.js';

/**
 * Set the status bar text.
 * @param {string} msg
 */
export function updateStatus(msg) {
    if (dom.statusText) dom.statusText.textContent = msg;
}
