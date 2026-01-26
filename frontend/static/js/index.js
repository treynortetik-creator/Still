/**
 * Main entry point for ContentMultiplier frontend modules.
 * This file imports and re-exports all modules, and sets up global variables
 * for backwards compatibility with inline scripts in HTML files.
 *
 * Usage in HTML files:
 *   <script type="module" src="/static/js/index.js"></script>
 *
 * After loading, the following globals are available:
 *   - Auth (authentication utilities)
 *   - Utils (utility functions)
 *   - api (API client)
 *   - escapeHtml, showToast, copyToClipboard, etc. (individual utility functions)
 */

// Import all modules
import Auth from '/static/js/auth.js';
import Utils, {
    escapeHtml,
    copyToClipboard,
    showToast,
    formatDate,
    formatRelativeDate,
    formatCurrency,
    debounce,
    truncate,
    generateId,
    isEmpty,
    storage
} from '/static/js/utils.js';
import { api, ApiError } from '/static/js/api-client.js';

// Re-export everything for ES6 module consumers
export {
    // Auth module
    Auth,

    // Utils module
    Utils,
    escapeHtml,
    copyToClipboard,
    showToast,
    formatDate,
    formatRelativeDate,
    formatCurrency,
    debounce,
    truncate,
    generateId,
    isEmpty,
    storage,

    // API client
    api,
    ApiError
};

// Default export for convenience
export default {
    Auth,
    Utils,
    api,
    ApiError
};
