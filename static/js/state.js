/**
 * state.js — Shared mutable application state.
 *
 * All modules import from here so there is a single source of truth.
 * Mutate via the exported setters; never import and reassign directly
 * from another module (ES module bindings are live but not settable
 * from outside the declaring module).
 */

/** Set of active indicator overlay keys (matches data-indicator attrs). */
export const activeIndicators = new Set(['sma20', 'volume']);

/** Most-recently fetched chart data — lets toggles re-render without a new fetch. */
let _lastChartData = null;
export const getLastChartData = () => _lastChartData;
export const setLastChartData = (data) => { _lastChartData = data; };

/** Socket.IO connection (lazy-initialised). */
let _socket = null;
export const getSocket = () => _socket;
export const setSocket = (s) => { _socket = s; };

/** setInterval handle for live-price polling. */
let _livePriceInterval = null;
export const getLivePriceInterval = () => _livePriceInterval;
export const setLivePriceInterval = (id) => { _livePriceInterval = id; };
