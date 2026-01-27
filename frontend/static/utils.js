/**
 * Shared utility functions for ContentMultiplier frontend.
 * Include this script on all pages that need these utilities.
 */

const Utils = {
    /**
     * Escape HTML to prevent XSS attacks.
     * @param {string} text - The text to escape
     * @returns {string} - The escaped HTML-safe text
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Copy text to clipboard and optionally show a toast notification.
     * @param {string} text - The text to copy
     * @param {boolean} showNotification - Whether to show a toast (default: true)
     */
    async copyToClipboard(text, showNotification = true) {
        try {
            await navigator.clipboard.writeText(text);
            if (showNotification) {
                this.showToast('Copied to clipboard!', 'success');
            }
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            if (showNotification) {
                this.showToast('Failed to copy to clipboard', 'error');
            }
            return false;
        }
    },

    /**
     * Copy text to clipboard with visual checkmark feedback on the button.
     * Shows a checkmark icon replacing the button content for 2 seconds.
     * @param {string} text - The text to copy
     * @param {HTMLElement|Event} buttonOrEvent - The button element or click event
     */
    async copyWithFeedback(text, buttonOrEvent) {
        // Get button element from event or direct reference
        const button = buttonOrEvent?.target?.closest('button') ||
                       buttonOrEvent?.currentTarget ||
                       buttonOrEvent;

        if (!button) {
            return this.copyToClipboard(text);
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
            this.showToast('Failed to copy to clipboard', 'error');
            return false;
        }
    },

    /**
     * Show a toast notification.
     * Creates the toast element if it doesn't exist.
     * @param {string} message - The message to display
     * @param {string} type - The type of toast: 'success', 'error', 'info' (default: 'success')
     * @param {number} duration - How long to show the toast in ms (default: 2000)
     */
    showToast(message, type = 'success', duration = 2000) {
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
    },

    /**
     * Format a date string for display.
     * @param {string} dateStr - ISO date string
     * @param {object} options - Intl.DateTimeFormat options
     * @returns {string} - Formatted date string
     */
    formatDate(dateStr, options = {}) {
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
    },

    /**
     * Format a number as currency.
     * @param {number} amount - The amount to format
     * @param {string} currency - Currency code (default: 'USD')
     * @returns {string} - Formatted currency string
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 4
        }).format(amount);
    },

    /**
     * Debounce a function call.
     * @param {Function} func - The function to debounce
     * @param {number} wait - The debounce delay in ms
     * @returns {Function} - The debounced function
     */
    debounce(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Truncate text to a maximum length.
     * @param {string} text - The text to truncate
     * @param {number} maxLength - Maximum length (default: 100)
     * @param {string} suffix - Suffix to add when truncated (default: '...')
     * @returns {string} - Truncated text
     */
    truncate(text, maxLength = 100, suffix = '...') {
        if (!text || text.length <= maxLength) return text || '';
        return text.substring(0, maxLength - suffix.length) + suffix;
    }
};

// For backwards compatibility, also expose as standalone functions
function escapeHtml(text) {
    return Utils.escapeHtml(text);
}

function copyToClipboard(text) {
    return Utils.copyToClipboard(text);
}

function copyWithFeedback(text, buttonOrEvent) {
    return Utils.copyWithFeedback(text, buttonOrEvent);
}

function showToast(message, type = 'success') {
    return Utils.showToast(message, type);
}
