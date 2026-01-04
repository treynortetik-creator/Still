// frontend/static/error-logger.js
/**
 * Error Logger - Sends errors to backend for tracking
 */
const ErrorLogger = {
    async log(errorType, errorMessage, endpoint = null, stackTrace = null, context = {}) {
        try {
            const token = typeof Auth !== 'undefined' && Auth.getToken ? Auth.getToken() : null;
            await fetch('/api/errors/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token && { 'Authorization': `Bearer ${token}` })
                },
                body: JSON.stringify({
                    error_type: errorType,
                    error_message: errorMessage,
                    endpoint: endpoint || window.location.pathname,
                    stack_trace: stackTrace,
                    additional_context: {
                        ...context,
                        browser: navigator.userAgent,
                        url: window.location.href,
                        timestamp: new Date().toISOString()
                    }
                })
            });
        } catch (e) {
            // Silently fail - don't create error loops
            console.error('Failed to log error:', e);
        }
    },

    // Map backend errors to user-friendly messages
    friendlyMessage(errorMessage) {
        const friendlyErrors = {
            'Still already retired': 'This pair was already merged.',
            'Winner still not found': 'One of these stills no longer exists.',
            'Loser still not found': 'One of these stills no longer exists.',
            'Still not found': 'This still no longer exists.',
            'Unauthorized': 'Please log in again.',
            'Network Error': 'Connection issue. Please check your internet.',
            'Failed to fetch': 'Connection issue. Please check your internet.',
        };
        return friendlyErrors[errorMessage] || errorMessage;
    }
};

// Global uncaught error handler
window.onerror = function(msg, url, line, col, error) {
    ErrorLogger.log('uncaught_error', msg, url, error?.stack, { line, col });
    return false; // Let default handler run too
};

// Unhandled promise rejection handler
window.onunhandledrejection = function(event) {
    const message = event.reason?.message || String(event.reason);
    ErrorLogger.log('unhandled_rejection', message, window.location.pathname, event.reason?.stack);
};
