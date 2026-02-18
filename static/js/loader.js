/**
 * loader.js — Dynamic HTML partial loader.
 *
 * Fetches HTML fragments from /partials/<name>.html and injects them
 * into a mount-point element in the shell index.html.
 *
 * Usage:
 *   await loadPartial('toolbar',       'mount-toolbar');
 *   await loadPartial('indicator-bar', 'mount-indicator-bar');
 *   // …or all at once:
 *   await loadAllPartials();
 */

/**
 * Fetch one HTML partial and inject it into a mount element.
 *
 * @param {string} name    - Partial filename without extension (e.g. 'toolbar')
 * @param {string} mountId - ID of the target container element
 * @returns {Promise<void>}
 */
export async function loadPartial(name, mountId) {
    const mount = document.getElementById(mountId);
    if (!mount) {
        console.warn(`[loader] Mount point #${mountId} not found.`);
        return;
    }

    const res = await fetch(`/partials/${name}.html`);
    if (!res.ok) {
        console.error(`[loader] Failed to load partial "${name}": ${res.status}`);
        return;
    }

    mount.innerHTML = await res.text();
}

/**
 * Mapping of partial name → mount-point ID.
 * Order is irrelevant — all fetches run in parallel.
 */
const PARTIALS = [
    ['toolbar', 'mount-toolbar'],
    ['indicator-bar', 'mount-indicator-bar'],
    ['sidebar', 'mount-sidebar'],
    ['signal-bar', 'mount-signal-bar'],
    ['chatbot', 'mount-chatbot'],
];

/**
 * Load all partials in parallel.
 * Resolves when every partial has been injected.
 * @returns {Promise<void>}
 */
export async function loadAllPartials() {
    await Promise.all(PARTIALS.map(([name, mountId]) => loadPartial(name, mountId)));
}
