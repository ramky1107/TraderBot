/**
 * chatbot.js — Floating AI chatbot widget logic.
 *
 * Exports:
 *   initChatbot()    — wire toggle/close/send events
 *   appendMessage()  — add a bubble to the chat panel
 *   sendMessage()    — POST to /api/chatbot and display reply
 */

import { API_URL } from './config.js';
import * as dom from './dom.js';

// ─── Message Rendering ────────────────────────────────────────────────────────

/**
 * Append a message bubble to the chat panel.
 * @param {string}          text
 * @param {'user'|'bot'}    sender
 */
export function appendMessage(text, sender) {
    if (!dom.chatbotMessages) return;

    const div = document.createElement('div');
    div.className = `chatbot-message ${sender}-message`;
    div.textContent = text;
    dom.chatbotMessages.appendChild(div);
    dom.chatbotMessages.scrollTop = dom.chatbotMessages.scrollHeight;
}

// ─── Send ─────────────────────────────────────────────────────────────────────

/**
 * Read the chatbot input, POST to /api/chatbot, display the reply.
 */
export async function sendMessage() {
    const msg = dom.chatbotInput?.value?.trim();
    if (!msg) return;

    appendMessage(msg, 'user');
    if (dom.chatbotInput) dom.chatbotInput.value = '';

    try {
        const res = await fetch(`${API_URL}/api/chatbot`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        });
        const data = await res.json();
        appendMessage(data.response || data.error || 'No response.', 'bot');
    } catch (err) {
        appendMessage(`Error: ${err.message}`, 'bot');
    }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

/**
 * Wire all chatbot event listeners.
 * Called once after partials are loaded.
 */
export function initChatbot() {
    dom.chatbotSend?.addEventListener('click', sendMessage);

    dom.chatbotInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter') sendMessage();
    });

    dom.chatbotToggle?.addEventListener('click', () => {
        dom.chatbotContainer?.classList.toggle('open');
    });

    dom.chatbotClose?.addEventListener('click', () => {
        dom.chatbotContainer?.classList.remove('open');
    });
}
