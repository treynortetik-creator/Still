/**
 * Authentication utilities for ContentMultiplier frontend.
 * Include this script on all protected pages.
 */

const Auth = {
    // Get the stored token
    getToken() {
        return localStorage.getItem('auth_token');
    },

    // Get stored user info
    getUser() {
        const user = localStorage.getItem('user');
        if (!user) return null;
        try {
            return JSON.parse(user);
        } catch (e) {
            // Clear corrupted data and return null
            localStorage.removeItem('user');
            return null;
        }
    },

    // Check if user is logged in
    isLoggedIn() {
        return !!this.getToken();
    },

    // Logout user
    logout() {
        const token = this.getToken();
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
    },

    // Get headers with auth token
    getHeaders(additionalHeaders = {}) {
        const token = this.getToken();
        const headers = {
            ...additionalHeaders
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    },

    // Fetch with auth and retry logic
    async fetchWithAuth(url, options = {}) {
        const maxRetries = 3;
        let lastError;

        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                const response = await fetch(url, {
                    ...options,
                    headers: this.getHeaders(options.headers || {})
                });

                // Handle 401 - redirect to login
                if (response.status === 401) {
                    this.logout();
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
    },

    // Require auth - redirect to login if not authenticated
    requireAuth() {
        if (!this.isLoggedIn()) {
            window.location.href = '/login.html';
            return false;
        }
        return true;
    },

    // Verify token is still valid
    async verifyToken() {
        const token = this.getToken();
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
                this.logout();
                return false;
            }
        } catch (err) {
            return false;
        }
    },

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Add user info to navbar
    updateNavbar() {
        const user = this.getUser();
        const navbarUserSection = document.getElementById('navbar-user');

        if (navbarUserSection && user) {
            // Escape email to prevent XSS
            const safeEmail = this.escapeHtml(user.email || '');
            navbarUserSection.innerHTML = `
                <a href="/admin/dashboard" class="text-gray-600 hover:text-gray-900 text-sm">
                    <svg class="w-5 h-5 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path>
                    </svg>
                    <span class="ml-1">Admin</span>
                </a>
                <a href="/settings.html" class="text-gray-600 hover:text-gray-900 text-sm ml-4">
                    <svg class="w-5 h-5 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    <span class="ml-1">Settings</span>
                </a>
                <span class="text-gray-600 text-sm ml-4">${safeEmail}</span>
                <button onclick="Auth.logout()" class="text-gray-600 hover:text-gray-900 text-sm ml-4">
                    Logout
                </button>
            `;
        } else if (navbarUserSection) {
            navbarUserSection.innerHTML = `
                <a href="/login.html" class="text-gray-600 hover:text-gray-900">Login</a>
                <a href="/register.html" class="ml-4 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700">
                    Get Started
                </a>
            `;
        }
    }
};

// Auto-update navbar when page loads
document.addEventListener('DOMContentLoaded', () => {
    Auth.updateNavbar();
});
