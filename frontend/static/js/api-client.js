/**
 * Centralized API client for ContentMultiplier frontend.
 * Provides consistent error handling, retries, and auth header management.
 *
 * Usage:
 *   import { api, ApiError } from '/static/js/api-client.js';
 *
 *   // GET request
 *   const data = await api.get('/api/personas');
 *
 *   // POST with JSON body
 *   const result = await api.post('/api/upload', { file: 'data' });
 *
 *   // With custom options
 *   const response = await api.fetch('/api/custom', { method: 'PATCH', body: data });
 */

// Custom error class for API errors
export class ApiError extends Error {
    constructor(message, status, detail = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.detail = detail;
    }
}

// Get auth token from localStorage
function getToken() {
    return localStorage.getItem('auth_token');
}

// Build headers with auth token
function buildHeaders(additionalHeaders = {}) {
    const token = getToken();
    const headers = { ...additionalHeaders };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// Handle auth-related redirects
function handleAuthRedirect() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    window.location.href = '/login.html';
}

/**
 * Core fetch wrapper with auth, retries, and error handling
 */
async function fetchWithAuth(url, options = {}) {
    const maxRetries = options.retries ?? 3;
    let lastError;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: buildHeaders(options.headers || {})
            });

            // Handle 401 - redirect to login
            if (response.status === 401) {
                handleAuthRedirect();
                throw new ApiError('Session expired. Please log in again.', 401);
            }

            // Handle 429 - rate limited
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After') || 60;
                throw new ApiError(`Rate limit exceeded. Try again in ${retryAfter} seconds.`, 429);
            }

            return response;
        } catch (err) {
            lastError = err;

            // Don't retry on auth errors or ApiErrors
            if (err instanceof ApiError) {
                throw err;
            }

            // Exponential backoff for network errors
            if (attempt < maxRetries - 1) {
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
            }
        }
    }

    throw lastError || new Error('Request failed after retries');
}

/**
 * Parse response and throw on error status
 */
async function parseResponse(response) {
    // Handle 204 No Content
    if (response.status === 204) {
        return null;
    }

    const contentType = response.headers.get('content-type');

    // Parse JSON responses
    if (contentType && contentType.includes('application/json')) {
        const data = await response.json();

        if (!response.ok) {
            throw new ApiError(
                data.detail || data.message || `Request failed with status ${response.status}`,
                response.status,
                data.detail
            );
        }

        return data;
    }

    // Handle text responses
    if (!response.ok) {
        const text = await response.text();
        throw new ApiError(text || `Request failed with status ${response.status}`, response.status);
    }

    return response;
}

/**
 * Main API client object
 */
export const api = {
    /**
     * Raw fetch with auth headers (returns Response object)
     */
    async fetch(url, options = {}) {
        return fetchWithAuth(url, options);
    },

    /**
     * GET request - parses JSON response
     */
    async get(url, options = {}) {
        const response = await fetchWithAuth(url, {
            method: 'GET',
            ...options
        });
        return parseResponse(response);
    },

    /**
     * POST request with JSON body
     */
    async post(url, data = null, options = {}) {
        const fetchOptions = {
            method: 'POST',
            ...options
        };

        if (data !== null) {
            fetchOptions.headers = {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            };
            fetchOptions.body = JSON.stringify(data);
        }

        const response = await fetchWithAuth(url, fetchOptions);
        return parseResponse(response);
    },

    /**
     * PUT request with JSON body
     */
    async put(url, data, options = {}) {
        const response = await fetchWithAuth(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            },
            body: JSON.stringify(data),
            ...options
        });
        return parseResponse(response);
    },

    /**
     * PATCH request with JSON body
     */
    async patch(url, data, options = {}) {
        const response = await fetchWithAuth(url, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            },
            body: JSON.stringify(data),
            ...options
        });
        return parseResponse(response);
    },

    /**
     * DELETE request
     */
    async delete(url, options = {}) {
        const response = await fetchWithAuth(url, {
            method: 'DELETE',
            ...options
        });
        return parseResponse(response);
    },

    /**
     * POST with FormData (for file uploads)
     */
    async upload(url, formData, options = {}) {
        const response = await fetchWithAuth(url, {
            method: 'POST',
            body: formData,
            ...options
            // Note: Don't set Content-Type header - browser sets it with boundary for FormData
        });
        return parseResponse(response);
    }
};

// Backwards compatibility: expose as global
if (typeof window !== 'undefined') {
    window.api = api;
    window.ApiError = ApiError;
}

export default api;
