/**
 * websocket.js — Socket.IO connection for real-time news updates.
 *
 * Lazy-initialised: the socket is created only on the first call to
 * initWebSocket(). Subsequent calls just emit 'activate_news' on the
 * existing connection.
 */

import { API_URL } from './config.js';
import { getSocket, setSocket } from './state.js';
import { renderNewsHeadlines } from './renderers.js';

/**
 * Initialise (or reuse) the Socket.IO connection.
 * Subscribes to 'new_news' events and forwards headlines to the renderer.
 *
 * @param {string} ticker - Active ticker to subscribe news for
 */
export function initWebSocket(ticker) {
    let socket = getSocket();

    if (socket) {
        // Already connected — just switch the ticker subscription
        socket.emit('activate_news', { ticker });
        return;
    }

    socket = io(API_URL);
    setSocket(socket);

    socket.on('connect', () => {
        console.log('[ws] Connected');
        socket.emit('activate_news', { ticker });
    });

    socket.on('new_news', data => {
        const headlines = data?.headlines || [];
        if (headlines.length > 0) renderNewsHeadlines(headlines);
    });

    socket.on('disconnect', () => console.log('[ws] Disconnected'));
}
