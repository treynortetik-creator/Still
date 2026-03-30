/**
 * Authentication utilities for ContentMultiplier frontend.
 *
 * Usage:
 *   import Auth, { getToken, getUser, isLoggedIn, logout, requireAuth } from '/static/js/auth.js';
 */

// Local escapeHtml to avoid circular dependency with utils.js
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Get the stored auth token
 * @returns {string|null} - The auth token or null
 */
export function getToken() {
    return localStorage.getItem('auth_token');
}

/**
 * Get stored user info
 * @returns {object|null} - The user object or null
 */
export function getUser() {
    const user = localStorage.getItem('user');
    if (!user) return null;
    try {
        return JSON.parse(user);
    } catch (e) {
        // Clear corrupted data and return null
        localStorage.removeItem('user');
        return null;
    }
}

/**
 * Check if user is logged in
 * @returns {boolean} - Whether user has an auth token
 */
export function isLoggedIn() {
    return !!getToken();
}

/**
 * Log out the user
 */
export function logout() {
    const token = getToken();
    if (token) {
        // Call logout endpoint (fire and forget)
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        }).catch(() => {});
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    window.location.href = '/login.html';
}

/**
 * Get headers with auth token
 * @param {object} additionalHeaders - Additional headers to merge
 * @returns {object} - Headers object with Authorization
 */
export function getHeaders(additionalHeaders = {}) {
    const token = getToken();
    const headers = { ...additionalHeaders };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * Fetch with auth and retry logic
 * @param {string} url - The URL to fetch
 * @param {object} options - Fetch options
 * @returns {Promise<Response>} - The fetch response
 */
export async function fetchWithAuth(url, options = {}) {
    const maxRetries = 3;
    let lastError;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: getHeaders(options.headers || {})
            });

            // Handle 401 - redirect to login
            if (response.status === 401) {
                logout();
                throw new Error('Session expired. Please log in again.');
            }

            // Handle 429 - rate limited
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After') || 60;
                throw new Error(`Rate limit exceeded. Try again in ${retryAfter} seconds.`);
            }

            return response;
        } catch (err) {
            lastError = err;

            // Don't retry on auth errors
            if (err.message.includes('Session expired') || err.message.includes('Rate limit')) {
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
 * Require auth - redirect to login if not authenticated
 * @returns {boolean} - Whether user is logged in
 */
export function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

/**
 * Verify token is still valid
 * @returns {Promise<boolean>} - Whether token is valid
 */
export async function verifyToken() {
    const token = getToken();
    if (!token) return false;

    try {
        const response = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const user = await response.json();
            localStorage.setItem('user', JSON.stringify(user));
            return true;
        } else {
            logout();
            return false;
        }
    } catch (err) {
        return false;
    }
}

/**
 * Update navbar with user info
 * Note: Uses escapeHtml() to sanitize user email before DOM insertion (XSS-safe)
 */
export function updateNavbar() {
    const user = getUser();
    const navbarUserSection = document.getElementById('navbar-user');

    if (navbarUserSection && user) {
        // XSS-safe: escapeHtml sanitizes user input before DOM insertion
        const safeEmail = escapeHtml(user.email || '');

        // Build navbar with sanitized content - static HTML with escaped user data
        const adminLink = document.createElement('a');
        adminLink.href = '/admin/dashboard';
        adminLink.className = 'text-still-muted hover:text-still-text text-sm';
        adminLink.innerHTML = '<svg class="w-5 h-5 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg><span class="ml-1">Admin</span>';

        const emailSpan = document.createElement('span');
        emailSpan.className = 'text-still-muted text-sm ml-4';
        emailSpan.textContent = safeEmail; // textContent is XSS-safe

        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'text-still-muted hover:text-still-text text-sm ml-4';
        logoutBtn.textContent = 'Logout';
        logoutBtn.onclick = () => logout();

        navbarUserSection.replaceChildren(adminLink, emailSpan, logoutBtn);
    } else if (navbarUserSection) {
        const loginLink = document.createElement('a');
        loginLink.href = '/login.html';
        loginLink.className = 'text-still-muted hover:text-still-text';
        loginLink.textContent = 'Login';

        const registerLink = document.createElement('a');
        registerLink.href = '/register.html';
        registerLink.className = 'ml-4 bg-still-copper text-white px-4 py-2 rounded-lg hover:bg-still-copper/80';
        registerLink.textContent = 'Get Started';

        navbarUserSection.replaceChildren(loginLink, registerLink);
    }
}

// Create Auth object for backwards compatibility
const Auth = {
    getToken,
    getUser,
    isLoggedIn,
    logout,
    getHeaders,
    fetchWithAuth,
    requireAuth,
    verifyToken,
    updateNavbar,
    // Legacy escapeHtml method (prefer using the utils version)
    escapeHtml
};

// Backwards compatibility: expose as global
if (typeof window !== 'undefined') {
    window.Auth = Auth;
}

// Auto-update navbar when page loads
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        updateNavbar();
    });
}

export default Auth;
