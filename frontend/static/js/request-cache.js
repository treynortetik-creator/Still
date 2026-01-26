/**
 * Simple request cache with TTL and deduplication.
 * Prevents redundant API calls within the same page session.
 *
 * Usage:
 *   import { cachedFetch, invalidateCache } from '/static/js/request-cache.js';
 *
 *   // Cached GET request (5 second default TTL)
 *   const data = await cachedFetch('/api/personas');
 *
 *   // Custom TTL (30 seconds)
 *   const data = await cachedFetch('/api/library', { ttl: 30000 });
 *
 *   // Force fresh fetch
 *   const data = await cachedFetch('/api/personas', { force: true });
 *
 *   // Invalidate specific cache entry
 *   invalidateCache('/api/personas');
 *
 *   // Invalidate all cache entries matching pattern
 *   invalidateCache('/api/personas', { pattern: true });
 */

// Cache storage: Map of URL -> { data, timestamp, promise }
const cache = new Map();

// In-flight requests: Map of URL -> Promise (for deduplication)
const pending = new Map();

// Default TTL: 5 seconds
const DEFAULT_TTL = 5000;

/**
 * Fetch with caching and request deduplication.
 * @param {string} url - The URL to fetch
 * @param {object} options - Options: ttl (ms), force (boolean), fetchOptions (passed to fetch)
 * @returns {Promise<any>} - Parsed JSON response
 */
export async function cachedFetch(url, options = {}) {
    const { ttl = DEFAULT_TTL, force = false, ...fetchOptions } = options;

    // Check cache first (unless force refresh)
    if (!force) {
        const cached = cache.get(url);
        if (cached && Date.now() - cached.timestamp < ttl) {
            return cached.data;
        }
    }

    // Check for in-flight request (deduplication)
    if (pending.has(url)) {
        return pending.get(url);
    }

    // Make the request
    const promise = (async () => {
        try {
            // Use api client if available, otherwise Auth.fetchWithAuth
            const response = typeof api !== 'undefined'
                ? await api.get(url, fetchOptions)
                : await Auth.fetchWithAuth(url, fetchOptions).then(r => r.json());

            // Cache the result
            cache.set(url, {
                data: response,
                timestamp: Date.now()
            });

            return response;
        } finally {
            // Remove from pending regardless of success/failure
            pending.delete(url);
        }
    })();

    // Track in-flight request
    pending.set(url, promise);

    return promise;
}

/**
 * Invalidate cache entries.
 * @param {string} url - URL or pattern to invalidate
 * @param {object} options - Options: pattern (boolean) - treat url as prefix pattern
 */
export function invalidateCache(url, options = {}) {
    if (options.pattern) {
        // Invalidate all matching prefix
        for (const key of cache.keys()) {
            if (key.startsWith(url)) {
                cache.delete(key);
            }
        }
    } else {
        cache.delete(url);
    }
}

/**
 * Clear entire cache.
 */
export function clearCache() {
    cache.clear();
}

/**
 * Get cache stats for debugging.
 */
export function getCacheStats() {
    return {
        size: cache.size,
        pending: pending.size,
        entries: Array.from(cache.keys())
    };
}

// Backwards compatibility: expose as globals
if (typeof window !== 'undefined') {
    window.cachedFetch = cachedFetch;
    window.invalidateCache = invalidateCache;
    window.clearCache = clearCache;
}

export default { cachedFetch, invalidateCache, clearCache, getCacheStats };
