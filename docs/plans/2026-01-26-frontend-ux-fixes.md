# Frontend UX Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three frontend UX issues: missing skeleton loaders, inconsistent error feedback, and redundant API calls.

**Architecture:** Add skeleton loaders to Workshop/Calendar pages (copying Reserve pattern), standardize all error handling on `showToast()`, and add a simple request cache to prevent duplicate fetches.

**Tech Stack:** Vanilla JS, CSS shimmer animations, existing `/static/js/` modules

---

## Task 1: Add Skeleton Loaders to Workshop Page

**Files:**
- Modify: `frontend/workshop.html` (lines 91-95 loading state, lines 108-110 grid)

**Step 1: Add skeleton CSS to Workshop page**

Add the skeleton-card CSS inside the existing `<style>` block (after line ~50):

```css
/* Loading skeleton */
.skeleton-card {
    height: 160px;
    background: linear-gradient(90deg, var(--surface-elevated) 0%, var(--surface-highlight) 50%, var(--surface-elevated) 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite linear;
    border-radius: var(--radius-lg);
}
```

**Step 2: Replace spinner with skeleton cards**

Replace the loading div (lines 91-95):

```html
<!-- Loading State -->
<div id="loading" class="text-center py-12">
    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-still-copper mx-auto"></div>
    <p class="mt-4 text-still-muted">Loading your content...</p>
</div>
```

With skeleton grid:

```html
<!-- Loading Skeletons -->
<div id="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
</div>
```

**Step 3: Test manually**

Open Workshop page in browser, verify:
1. Skeleton cards appear on initial load
2. Skeleton cards match 3-column grid layout
3. Skeleton cards have shimmer animation
4. Real content replaces skeletons after load

**Step 4: Commit**

```bash
git add frontend/workshop.html
git commit -m "feat(workshop): add skeleton loaders for better perceived performance

Replace plain spinner with shimmer skeleton cards that match content shape.
Reuses skeleton pattern from Reserve page.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Add Skeleton Loaders to Calendar Page

**Files:**
- Modify: `frontend/calendar.html` (lines 89-93 calendar grid, lines 100 unscheduled list)

**Step 1: Add skeleton CSS to Calendar page**

Add to `<style>` block or create one after line ~47:

```css
<style>
    /* Calendar skeleton */
    .skeleton-day {
        height: 100px;
        background: linear-gradient(90deg, var(--surface-elevated) 0%, var(--surface-highlight) 50%, var(--surface-elevated) 100%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite linear;
    }
    .skeleton-sidebar-item {
        height: 60px;
        background: linear-gradient(90deg, var(--surface-elevated) 0%, var(--surface-highlight) 50%, var(--surface-elevated) 100%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite linear;
        border-radius: var(--radius-md);
    }
</style>
```

**Step 2: Add skeleton days to calendar grid**

Modify the calendar-grid div (line 90-92) to include initial skeleton days:

```html
<!-- Calendar Days -->
<div id="calendar-grid" class="grid grid-cols-7">
    <!-- Skeleton days shown during load -->
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-r border-b border-still-border"></div>
    <div class="skeleton-day border-b border-still-border"></div>
</div>
```

**Step 3: Add skeleton items to unscheduled list**

Modify unscheduled-list div (around line 100) to include initial skeletons:

```html
<div id="unscheduled-list" class="space-y-3 max-h-[600px] overflow-y-auto">
    <!-- Skeleton items shown during load -->
    <div class="skeleton-sidebar-item"></div>
    <div class="skeleton-sidebar-item"></div>
    <div class="skeleton-sidebar-item"></div>
</div>
```

**Step 4: Test manually**

Open Calendar page in browser, verify:
1. Skeleton grid appears in calendar area on load
2. Skeleton items appear in sidebar on load
3. Real content replaces skeletons after API response

**Step 5: Commit**

```bash
git add frontend/calendar.html
git commit -m "feat(calendar): add skeleton loaders for calendar grid and sidebar

Add shimmer skeleton placeholders for calendar days and unscheduled
content list during initial load.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add Skeleton to Results Page Processing View

**Files:**
- Modify: `frontend/results.html` (lines 170-230 split-view-right section)

**Step 1: Add skeleton for stills preview area**

The results page already has good progress indicators. Add a skeleton preview for the "stills being extracted" state. Find the split-view-left section and add skeleton stills:

```css
<style>
    .skeleton-still {
        height: 80px;
        background: linear-gradient(90deg, var(--surface-elevated) 0%, var(--surface-highlight) 50%, var(--surface-elevated) 100%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite linear;
        border-radius: var(--radius-md);
    }
</style>
```

**Step 2: Add skeleton stills placeholder in split-view-left**

Find the stills container in split-view-left and add:

```html
<div id="stills-skeleton" class="space-y-3">
    <div class="skeleton-still"></div>
    <div class="skeleton-still"></div>
    <div class="skeleton-still"></div>
</div>
```

**Step 3: Update JS to hide skeleton when stills load**

In the function that renders stills, add:

```javascript
document.getElementById('stills-skeleton')?.classList.add('hidden');
```

**Step 4: Test manually**

Open Results page during processing, verify:
1. Skeleton stills appear in left panel during distillation
2. Real stills replace skeletons when extracted
3. Progress steps continue to work correctly

**Step 5: Commit**

```bash
git add frontend/results.html
git commit -m "feat(results): add skeleton loaders for stills during processing

Show placeholder skeleton stills in left panel while content is being
distilled, providing better visual feedback during processing.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Standardize Error Handling - Workshop Page

**Files:**
- Modify: `frontend/workshop.html` (multiple error handling locations)

**Step 1: Fix loadOutputs error handling (line 362)**

Current:
```javascript
console.error('Error loading outputs:', err);
```

Change to:
```javascript
console.error('Error loading outputs:', err);
showToast('Failed to load content', 'error');
```

Note: Line 481-482 already has showToast, this is correct.

**Step 2: Fix saveOutput error handling (line 601)**

Current pattern already correct - has showToast on line 605.

**Step 3: Fix loadPersonas error handling (line 828)**

Current:
```javascript
console.error('Failed to load personas:', err);
```

Change to:
```javascript
console.error('Failed to load personas:', err);
showToast('Failed to load personas', 'error');
```

**Step 4: Test manually**

1. Disconnect network, open Workshop - should see toast error
2. Verify console still logs errors for debugging

**Step 5: Commit**

```bash
git add frontend/workshop.html
git commit -m "fix(workshop): add toast notifications for all error states

Ensure all error paths show user-visible toast notifications instead
of failing silently with console.error only.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Standardize Error Handling - Reserve Page

**Files:**
- Modify: `frontend/reserve.html` (lines 1218, 1265, 1293, 1310, 1453, 1890, 2020)

**Step 1: Audit current error patterns**

Check each console.error and verify showToast is called:
- Line 1218 (loadExamples): Add `showToast('Failed to load examples', 'error');`
- Line 1265 (loadPersonas): Add `showToast('Failed to load personas', 'error');`
- Line 1293 (loadFilters): Add `showToast('Failed to load filters', 'error');`
- Line 1310 (loadSourceFilters): Add `showToast('Failed to load sources', 'error');`
- Line 1453 (loadReserve): Add `showToast('Failed to load Reserve', 'error');`
- Line 1890/2020 (SOT): Already has showToast calls

**Step 2: Add missing showToast calls**

For each location above missing a toast, add after the console.error line.

**Step 3: Test manually**

1. Block API calls in devtools, verify toast appears
2. Verify reserve page still loads what it can

**Step 4: Commit**

```bash
git add frontend/reserve.html
git commit -m "fix(reserve): add toast notifications for all error states

Ensure filter, persona, and library load errors show user-visible
notifications instead of failing silently.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Standardize Error Handling - Settings Page

**Files:**
- Modify: `frontend/settings.html` (lines 733, 971, 1288, 1430)

**Step 1: Fix loadPersonas (line 733)**

Already has showToast on line 734 - verify it's after console.error.

**Step 2: Fix loadRules (line 971)**

Current:
```javascript
console.error('Failed to load rules:', err);
```

Add:
```javascript
showToast('Failed to load memory rules', 'error');
```

**Step 3: Fix loadWebhooks (line 1288)**

Current:
```javascript
console.error('Failed to load webhooks:', err);
```

Add:
```javascript
showToast('Failed to load webhooks', 'error');
```

**Step 4: Fix getSecretKey (line 1430)**

Current:
```javascript
console.error('Failed to get secret key:', err);
```

Add:
```javascript
showToast('Failed to get webhook secret', 'error');
```

**Step 5: Commit**

```bash
git add frontend/settings.html
git commit -m "fix(settings): add toast notifications for all error states

Ensure memory rules, webhooks, and secret key errors show user-visible
notifications instead of failing silently.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Standardize Error Handling - Autopilot Page

**Files:**
- Modify: `frontend/autopilot.html` (lines 288, 311, 324, 523, 541, 560, 580, 603, 681, 698)

**Step 1: Add showToast to all error handlers**

For each console.error location, add corresponding showToast:

```javascript
// Line 288 - loadPersonas
showToast('Failed to load personas', 'error');

// Line 311 - loadStats
showToast('Failed to load stats', 'error');

// Line 324 - loadSources
showToast('Failed to load sources', 'error');

// Line 523 - saveSource
showToast('Failed to save source', 'error');

// Line 541 - toggleSource
showToast('Failed to toggle source', 'error');

// Line 560 - deleteSource
showToast('Failed to delete source', 'error');

// Line 580 - checkSource
showToast('Failed to check source', 'error');

// Line 603 - loadItems
showToast('Failed to load items', 'error');

// Line 681 - processItem
showToast('Failed to process item', 'error');

// Line 698 - skipItem
showToast('Failed to skip item', 'error');
```

**Step 2: Commit**

```bash
git add frontend/autopilot.html
git commit -m "fix(autopilot): add toast notifications for all error states

Ensure all autopilot operations show user-visible error notifications
instead of failing silently with console.error only.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Create Request Cache Module

**Files:**
- Create: `frontend/static/js/request-cache.js`

**Step 1: Write the request cache module**

```javascript
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
```

**Step 2: Test the module**

```javascript
// In browser console:
const { cachedFetch } = await import('/static/js/request-cache.js');

// First call - hits API
await cachedFetch('/api/personas');

// Second call within 5s - returns cached
await cachedFetch('/api/personas');

// Force refresh
await cachedFetch('/api/personas', { force: true });
```

**Step 3: Commit**

```bash
git add frontend/static/js/request-cache.js
git commit -m "feat: add request cache module for API call deduplication

Provides cachedFetch() with TTL-based caching and in-flight request
deduplication to prevent redundant API calls.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Integrate Request Cache - Reserve Page

**Files:**
- Modify: `frontend/reserve.html` (add script import, update fetch calls)

**Step 1: Add script import**

After the existing module imports (around line 45), add:

```html
<script type="module">
    import { cachedFetch, invalidateCache } from '/static/js/request-cache.js';
    window.cachedFetch = cachedFetch;
    window.invalidateCache = invalidateCache;
</script>
```

**Step 2: Update loadPersonas to use cache**

Find the loadPersonas function and change:

```javascript
const response = await Auth.fetchWithAuth('/api/personas');
```

To:

```javascript
const data = await cachedFetch('/api/personas', { ttl: 30000 });
```

**Step 3: Update loadFilters to use cache**

Change the filters fetch to use cachedFetch with 60s TTL (filters rarely change):

```javascript
const data = await cachedFetch('/api/library/filters', { ttl: 60000 });
```

**Step 4: Update loadSourceFilters to use cache**

```javascript
const data = await cachedFetch('/api/library/sources', { ttl: 60000 });
```

**Step 5: Invalidate cache on mutations**

After successful still creation/update/delete, invalidate relevant caches:

```javascript
// After creating still
invalidateCache('/api/library', { pattern: true });

// After updating still
invalidateCache('/api/library', { pattern: true });

// After deleting still
invalidateCache('/api/library', { pattern: true });
```

**Step 6: Test manually**

1. Open Reserve page, check Network tab
2. Navigate away and back - should see fewer API calls
3. Create/update/delete still - should see fresh data

**Step 7: Commit**

```bash
git add frontend/reserve.html
git commit -m "feat(reserve): integrate request cache to reduce API calls

Use cachedFetch for personas, filters, and sources with appropriate
TTLs. Invalidate cache on mutations.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Integrate Request Cache - Settings Page

**Files:**
- Modify: `frontend/settings.html` (add script import, update fetch calls)

**Step 1: Add script import**

```html
<script type="module">
    import { cachedFetch, invalidateCache } from '/static/js/request-cache.js';
    window.cachedFetch = cachedFetch;
    window.invalidateCache = invalidateCache;
</script>
```

**Step 2: Update persona/rules/webhooks/brand-voice fetches**

Use cachedFetch with appropriate TTLs:

```javascript
// Personas - 30s TTL
const data = await cachedFetch('/api/personas', { ttl: 30000 });

// Memory rules - 30s TTL
const data = await cachedFetch('/api/memory/rules', { ttl: 30000 });

// Webhooks - 30s TTL
const data = await cachedFetch('/api/webhooks', { ttl: 30000 });

// Brand voice - 60s TTL
const data = await cachedFetch('/api/brand-voice', { ttl: 60000 });
```

**Step 3: Invalidate on mutations**

After CRUD operations, invalidate respective caches.

**Step 4: Commit**

```bash
git add frontend/settings.html
git commit -m "feat(settings): integrate request cache to reduce API calls

Use cachedFetch for personas, rules, webhooks, and brand voice data.
Invalidate cache on mutations.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Workshop skeleton loaders | workshop.html |
| 2 | Calendar skeleton loaders | calendar.html |
| 3 | Results skeleton loaders | results.html |
| 4 | Workshop error standardization | workshop.html |
| 5 | Reserve error standardization | reserve.html |
| 6 | Settings error standardization | settings.html |
| 7 | Autopilot error standardization | autopilot.html |
| 8 | Create request cache module | static/js/request-cache.js |
| 9 | Reserve cache integration | reserve.html |
| 10 | Settings cache integration | settings.html |

**Total: 10 tasks, ~30-40 commits**
