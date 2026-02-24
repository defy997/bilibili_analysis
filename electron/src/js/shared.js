/**
 * BiliMood · Shared Frontend Utilities
 * Loaded via <script src="js/shared.js"></script> before each page's own
 * inline <script> block.  Uses var so redeclaration in page scripts is safe.
 */

'use strict';

/* ── Constants ─────────────────────────────────────────────────────── */
var API_BASE = 'http://118.25.39.91:8000';

/* ── Theme ─────────────────────────────────────────────────────────── */

/**
 * Apply a background colour + opacity to the page.
 * Works for both body-background pages and #main-container pages.
 */
function applyTheme(bgColor, opacity) {
    const hex = bgColor.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);

    const bg = `rgba(${r}, ${g}, ${b}, ${opacity})`;
    console.log('[Theme] applyTheme called:', bgColor, opacity, '→', bg);
    document.body.style.background = bg;  // overrides any CSS gradient
    console.log('[Theme] body.style.background after set:', document.body.style.background);

    const container = document.getElementById('main-container');
    console.log('[Theme] #main-container found:', !!container);
    if (container) {
        container.style.background = bg;
        console.log('[Theme] container.style.background after set:', container.style.background);
    }

    // Inject / update dynamic overrides for glass-panel, drag-area, stat-card
    let style = document.getElementById('dynamic-theme');
    if (!style) {
        style = document.createElement('style');
        style.id = 'dynamic-theme';
        document.head.appendChild(style);
    }
    style.textContent = `
        .glass-panel   { background: rgba(${r}, ${g}, ${b}, ${opacity * 0.6}) !important; }
        .drag-area     { background-color: rgba(${r}, ${g}, ${b}, ${opacity * 0.8}) !important; }
        .stat-card:hover { background: rgba(${r}, ${g}, ${b}, ${opacity * 0.4}) !important; }
    `;
}

/** Fetch theme config and apply it. Called during DOMContentLoaded. */
async function loadThemeFromConfig() {
    try {
        console.log('[Theme] loadThemeFromConfig: fetching', `${API_BASE}/api/config/`);
        const resp = await fetch(`${API_BASE}/api/config/`, { credentials: 'include' });
        console.log('[Theme] fetch status:', resp.status);
        const result = await resp.json();
        console.log('[Theme] api/config/ response:', JSON.stringify(result).substring(0, 200));
        if (result.success && result.data?.ui_config) {
            const { background_color, opacity } = result.data.ui_config;
            console.log('[Theme] ui_config:', background_color, opacity);
            if (background_color && opacity !== undefined) {
                applyTheme(background_color, opacity);
            } else {
                console.warn('[Theme] background_color or opacity missing');
            }
        } else {
            console.warn('[Theme] result.success=', result.success, 'ui_config=', result.data?.ui_config);
        }
    } catch (err) {
        console.error('[Theme] Failed to load config:', err);
    }
}

/* ── Loading indicator ─────────────────────────────────────────────── */

/** Show or hide the #loading-indicator element. */
function showLoading(show) {
    const loader = document.getElementById('loading-indicator');
    if (!loader) return;
    loader.classList.toggle('hidden', !show);
}

/* ── API helper ────────────────────────────────────────────────────── */

/**
 * Thin wrapper around fetch() that:
 *  - prepends API_BASE when path starts with '/'
 *  - always resolves to the parsed JSON body
 *  - throws an enriched Error on non-2xx responses
 */
async function apiFetch(path, options = {}) {
    const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
    const resp = await fetch(url, options);
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) {
        const err = new Error(body.error || `HTTP ${resp.status}`);
        err.status = resp.status;
        err.data   = body;
        throw err;
    }
    return body;
}

/* ── Toast notification (shared version) ──────────────────────────── */
/**
 * Shows a brief toast.  If the page has its own #toast element, uses it;
 * otherwise creates a temporary one.
 */
function showSharedToast(message, type = 'info', duration = 2500) {
    const colors = {
        info:    'bg-blue-500/80',
        success: 'bg-green-500/80',
        error:   'bg-red-500/80',
        warning: 'bg-yellow-500/80',
    };
    const div = document.createElement('div');
    div.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg text-white text-sm z-50
                     ${colors[type] || colors.info} shadow-lg backdrop-blur-sm`;
    div.textContent = message;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), duration);
}
