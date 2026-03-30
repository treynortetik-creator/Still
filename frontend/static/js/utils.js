/**
 * Shared utility functions for ContentMultiplier frontend.
 *
 * Usage:
 *   import { escapeHtml, showToast, copyToClipboard, formatDate, debounce, truncate } from '/static/js/utils.js';
 */

/**
 * Escape HTML to prevent XSS attacks.
 * @param {string} text - The text to escape
 * @returns {string} - The escaped HTML-safe text
 */
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Copy text to clipboard and optionally show a toast notification.
 * @param {string} text - The text to copy
 * @param {boolean} showNotification - Whether to show a toast (default: true)
 * @returns {Promise<boolean>} - Whether the copy succeeded
 */
export async function copyToClipboard(text, showNotification = true) {
    try {
        await navigator.clipboard.writeText(text);
        if (showNotification) {
            showToast('Copied to clipboard!', 'success');
        }
        return true;
    } catch (err) {
        console.error('Failed to copy:', err);
        if (showNotification) {
            showToast('Failed to copy to clipboard', 'error');
        }
        return false;
    }
}

/**
 * Copy text to clipboard with visual checkmark feedback on the button.
 * Shows a checkmark icon replacing the button content for 2 seconds.
 * @param {string} text - The text to copy
 * @param {HTMLElement|Event} buttonOrEvent - The button element or click event
 * @returns {Promise<boolean>} - Whether the copy succeeded
 */
export async function copyWithFeedback(text, buttonOrEvent) {
    // Get button element from event or direct reference
    const button = buttonOrEvent?.target?.closest('button') ||
                   buttonOrEvent?.currentTarget ||
                   buttonOrEvent;

    if (!button) {
        return copyToClipboard(text);
    }

    try {
        await navigator.clipboard.writeText(text);

        // Store original content
        const originalChildren = Array.from(button.childNodes).map(node => node.cloneNode(true));
        const originalWidth = button.offsetWidth;

        // Set minimum width to prevent button from shrinking
        button.style.minWidth = `${originalWidth}px`;

        // Clear button and add checkmark using DOM methods
        button.textContent = '';

        const wrapper = document.createElement('span');
        wrapper.className = 'inline-flex items-center gap-1 text-still-green';

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'w-4 h-4');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('viewBox', '0 0 24 24');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('d', 'M5 13l4 4L19 7');

        svg.appendChild(path);
        wrapper.appendChild(svg);
        wrapper.appendChild(document.createTextNode(' Copied!'));
        button.appendChild(wrapper);
        button.classList.add('copy-success');

        // Restore after 2 seconds
        setTimeout(() => {
            button.textContent = '';
            originalChildren.forEach(child => button.appendChild(child));
            button.style.minWidth = '';
            button.classList.remove('copy-success');
        }, 2000);

        return true;
    } catch (err) {
        console.error('Failed to copy:', err);
        showToast('Failed to copy to clipboard', 'error');
        return false;
    }
}

/**
 * Show a toast notification.
 * Creates the toast element if it doesn't exist.
 * @param {string} message - The message to display
 * @param {string} type - The type of toast: 'success', 'error', 'info', 'warning' (default: 'success')
 * @param {number} duration - How long to show the toast in ms (default: 2000)
 */
export function showToast(message, type = 'success', duration = 2000) {
    // Try to find existing toast element
    let toast = document.getElementById('utils-toast');

    // Create toast if it doesn't exist
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'utils-toast';
        toast.className = 'fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg transition-all duration-300 transform translate-y-full opacity-0 z-50';
        document.body.appendChild(toast);
    }

    // Set colors based on type
    const colors = {
        success: 'bg-still-green text-white',
        error: 'bg-still-error text-white',
        info: 'bg-blue-500 text-white',
        warning: 'bg-still-amber text-still-bg'
    };

    // Reset classes and set new ones
    toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg transition-all duration-300 transform z-50 ${colors[type] || colors.success}`;
    toast.textContent = message;

    // Show toast
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-full', 'opacity-0');
    });

    // Hide toast after duration
    setTimeout(() => {
        toast.classList.add('translate-y-full', 'opacity-0');
    }, duration);
}

/**
 * Format a date string for display.
 * @param {string} dateStr - ISO date string
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string} - Formatted date string
 */
export function formatDate(dateStr, options = {}) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('en-US', { ...defaultOptions, ...options });
}

/**
 * Format a date as relative time (e.g., "2 hours ago", "yesterday").
 * @param {string} dateStr - ISO date string
 * @returns {string} - Relative time string
 */
export function formatRelativeDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'today';
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
}

/**
 * Format a number as currency.
 * @param {number} amount - The amount to format
 * @param {string} currency - Currency code (default: 'USD')
 * @returns {string} - Formatted currency string
 */
export function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 4
    }).format(amount);
}

/**
 * Debounce a function call.
 * @param {Function} func - The function to debounce
 * @param {number} wait - The debounce delay in ms (default: 300)
 * @returns {Function} - The debounced function
 */
export function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Truncate text to a maximum length.
 * @param {string} text - The text to truncate
 * @param {number} maxLength - Maximum length (default: 100)
 * @param {string} suffix - Suffix to add when truncated (default: '...')
 * @returns {string} - Truncated text
 */
export function truncate(text, maxLength = 100, suffix = '...') {
    if (!text || text.length <= maxLength) return text || '';
    return text.substring(0, maxLength - suffix.length) + suffix;
}

/**
 * Generate a unique ID string
 * @returns {string} - A unique identifier
 */
export function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Check if a value is empty (null, undefined, empty string, or empty array)
 * @param {*} value - The value to check
 * @returns {boolean} - Whether the value is empty
 */
export function isEmpty(value) {
    if (value == null) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'object') return Object.keys(value).length === 0;
    return false;
}

/**
 * Local storage helpers with JSON serialization and error handling
 */
export const storage = {
    get(key, defaultValue = null) {
        try {
            const value = localStorage.getItem(key);
            if (value === null) return defaultValue;
            return JSON.parse(value);
        } catch (e) {
            console.error('Storage get error:', e);
            return defaultValue;
        }
    },

    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('Storage set error:', e);
            return false;
        }
    },

    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('Storage remove error:', e);
            return false;
        }
    }
};

// Create Utils object for backwards compatibility
const Utils = {
    escapeHtml,
    copyToClipboard,
    copyWithFeedback,
    showToast,
    formatDate,
    formatRelativeDate,
    formatCurrency,
    debounce,
    truncate,
    generateId,
    isEmpty,
    storage
};

// Backwards compatibility: expose as globals
if (typeof window !== 'undefined') {
    window.Utils = Utils;
    window.escapeHtml = escapeHtml;
    window.copyToClipboard = copyToClipboard;
    window.copyWithFeedback = copyWithFeedback;
    window.showToast = showToast;
    window.formatDate = formatDate;
    window.formatRelativeDate = formatRelativeDate;
    window.formatCurrency = formatCurrency;
    window.debounce = debounce;
    window.truncate = truncate;
}

export default Utils;
