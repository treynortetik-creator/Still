# Audit Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix non-security issues identified in comprehensive audit (theming, accessibility, API, frontend improvements)

**Architecture:** Incremental fixes organized by category - CSS theme variables first (enables all other theme fixes), then frontend fixes, then backend fixes

**Tech Stack:** FastAPI, Jinja2, Vanilla JS, Tailwind CSS, CSS Custom Properties

---

## Phase 1: CSS Theme Infrastructure

### Task 1: Add Platform Color CSS Variables

**Files:**
- Modify: `frontend/static/styles.css`

**Step 1: Add platform color variables to :root (dark theme)**

Add after line 27 (after `--still-gradient-hover-end`):

```css
    /* Platform colors - dark theme */
    --platform-linkedin-bg: rgba(59, 130, 246, 0.2);
    --platform-linkedin-text: #60A5FA;
    --platform-linkedin-border: #3B82F6;
    --platform-twitter-bg: rgba(99, 102, 241, 0.2);
    --platform-twitter-text: #818CF8;
    --platform-twitter-border: #6366F1;
    --platform-email-bg: rgba(168, 85, 247, 0.2);
    --platform-email-text: #C084FC;
    --platform-email-border: #A855F7;
    --platform-midjourney-bg: rgba(59, 130, 246, 0.2);
    --platform-midjourney-text: #60A5FA;
    --platform-midjourney-border: #3B82F6;
    --platform-dalle-bg: rgba(34, 197, 94, 0.2);
    --platform-dalle-text: #4ADE80;
    --platform-dalle-border: #22C55E;
    --platform-stable-diffusion-bg: rgba(168, 85, 247, 0.2);
    --platform-stable-diffusion-text: #C084FC;
    --platform-stable-diffusion-border: #A855F7;

    /* Content type colors */
    --atom-data-bg: rgba(59, 130, 246, 0.2);
    --atom-data-text: #60A5FA;
    --atom-insight-bg: rgba(168, 85, 247, 0.2);
    --atom-insight-text: #C084FC;
    --atom-quote-bg: rgba(168, 85, 247, 0.2);
    --atom-quote-text: #C084FC;
    --atom-stat-bg: rgba(34, 197, 94, 0.2);
    --atom-stat-text: #4ADE80;

    /* Score colors */
    --score-high-bg: rgba(59, 130, 246, 0.15);
    --score-high-text: #60A5FA;
    --score-high-border: #3B82F6;
```

**Step 2: Add light theme overrides**

Add after line 90 (inside `[data-theme="light"]` block):

```css
    /* Platform colors - light theme */
    --platform-linkedin-bg: rgba(59, 130, 246, 0.1);
    --platform-linkedin-text: #2563EB;
    --platform-linkedin-border: #3B82F6;
    --platform-twitter-bg: rgba(99, 102, 241, 0.1);
    --platform-twitter-text: #4F46E5;
    --platform-twitter-border: #6366F1;
    --platform-email-bg: rgba(168, 85, 247, 0.1);
    --platform-email-text: #7C3AED;
    --platform-email-border: #A855F7;
    --platform-midjourney-bg: rgba(59, 130, 246, 0.1);
    --platform-midjourney-text: #2563EB;
    --platform-midjourney-border: #3B82F6;
    --platform-dalle-bg: rgba(34, 197, 94, 0.1);
    --platform-dalle-text: #16A34A;
    --platform-dalle-border: #22C55E;
    --platform-stable-diffusion-bg: rgba(168, 85, 247, 0.1);
    --platform-stable-diffusion-text: #7C3AED;
    --platform-stable-diffusion-border: #A855F7;

    /* Content type colors - light theme */
    --atom-data-bg: rgba(59, 130, 246, 0.1);
    --atom-data-text: #2563EB;
    --atom-insight-bg: rgba(168, 85, 247, 0.1);
    --atom-insight-text: #7C3AED;
    --atom-quote-bg: rgba(168, 85, 247, 0.1);
    --atom-quote-text: #7C3AED;
    --atom-stat-bg: rgba(34, 197, 94, 0.1);
    --atom-stat-text: #16A34A;

    /* Score colors - light theme */
    --score-high-bg: rgba(59, 130, 246, 0.1);
    --score-high-text: #2563EB;
    --score-high-border: #3B82F6;
```

**Step 3: Add utility classes for platforms**

Add at end of file (after print styles):

```css
/* ============================================
   PLATFORM COLOR UTILITIES
   ============================================ */

.platform-linkedin { background: var(--platform-linkedin-bg); color: var(--platform-linkedin-text); }
.platform-twitter { background: var(--platform-twitter-bg); color: var(--platform-twitter-text); }
.platform-email { background: var(--platform-email-bg); color: var(--platform-email-text); }
.platform-midjourney { background: var(--platform-midjourney-bg); color: var(--platform-midjourney-text); }
.platform-dalle { background: var(--platform-dalle-bg); color: var(--platform-dalle-text); }
.platform-stable-diffusion { background: var(--platform-stable-diffusion-bg); color: var(--platform-stable-diffusion-text); }

.atom-data { background: var(--atom-data-bg); color: var(--atom-data-text); }
.atom-insight { background: var(--atom-insight-bg); color: var(--atom-insight-text); }
.atom-quote { background: var(--atom-quote-bg); color: var(--atom-quote-text); }
.atom-stat { background: var(--atom-stat-bg); color: var(--atom-stat-text); }

.score-high { background: var(--score-high-bg); color: var(--score-high-text); border-color: var(--score-high-border); }

/* Email header styling */
.email-header {
    background: var(--platform-email-bg);
    border-color: var(--platform-email-border);
}
```

**Step 4: Verify file saved correctly**

Visually inspect the CSS file to ensure variables are properly nested and formatted.

**Step 5: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat: add platform and content type color CSS variables for theme support"
```

---

## Phase 2: Frontend Theme Fixes

### Task 2: Fix results.html Hardcoded Colors

**Files:**
- Modify: `frontend/results.html`

**Step 1: Update atom filter buttons (lines 172, 174)**

Replace:
```html
<button class="atom-filter px-3 py-1 rounded-full bg-blue-900/30 text-blue-400 text-sm" data-type="data">Data</button>
```

With:
```html
<button class="atom-filter px-3 py-1 rounded-full atom-data text-sm" data-type="data">Data</button>
```

Replace:
```html
<button class="atom-filter px-3 py-1 rounded-full bg-purple-900/30 text-purple-400 text-sm" data-type="insight">Insights</button>
```

With:
```html
<button class="atom-filter px-3 py-1 rounded-full atom-insight text-sm" data-type="insight">Insights</button>
```

**Step 2: Update getScoreColors function (around line 518)**

Replace:
```javascript
if (score >= 70) return { bg: 'bg-blue-900/20', text: 'text-blue-400', border: 'border-blue-400' };
```

With:
```javascript
if (score >= 70) return { bg: 'score-high', text: '', border: '' };
```

Note: This returns a single class that handles all three properties.

**Step 3: Update platform colors object (around line 587)**

Replace:
```javascript
'midjourney': 'bg-blue-900/30 text-blue-400',
```

With:
```javascript
'midjourney': 'platform-midjourney',
```

Replace:
```javascript
'stable_diffusion': 'bg-purple-900/30 text-purple-400'
```

With:
```javascript
'stable_diffusion': 'platform-stable-diffusion',
```

**Step 4: Update email header (around line 686)**

Replace:
```javascript
<div class="mb-3 p-3 bg-blue-900/20 rounded border border-blue-900/30">
```

With:
```javascript
<div class="mb-3 p-3 email-header rounded border">
```

**Step 5: Update version step labels (lines 861, 867)**

Replace:
```javascript
<strong class="text-blue-400">Step 1 (Draft):</strong>
```

With:
```javascript
<strong style="color: var(--platform-linkedin-text);">Step 1 (Draft):</strong>
```

Replace:
```javascript
<strong class="text-blue-400">Step 2 (Edited):</strong>
```

With:
```javascript
<strong style="color: var(--platform-linkedin-text);">Step 2 (Edited):</strong>
```

**Step 6: Fix error message escaping (line 960)**

Replace:
```javascript
<p class="text-still-error">Failed to load results: ${err.message}</p>
```

With:
```javascript
<p class="text-still-error">Failed to load results: ${escapeHtml(err.message)}</p>
```

**Step 7: Commit**

```bash
git add frontend/results.html
git commit -m "fix: replace hardcoded colors with theme-aware CSS variables in results.html"
```

---

### Task 3: Fix calendar.html Hardcoded Colors

**Files:**
- Modify: `frontend/calendar.html`

**Step 1: Update platform colors object (around line 217-219)**

Replace:
```javascript
linkedin: { bg: 'bg-blue-900/30', border: 'border-blue-500', text: 'text-blue-400' },
```

With:
```javascript
linkedin: { bg: 'platform-linkedin', border: '', text: '' },
```

Replace:
```javascript
email: { bg: 'bg-purple-900/30', border: 'border-purple-500', text: 'text-purple-400' },
```

With:
```javascript
email: { bg: 'platform-email', border: '', text: '' },
```

**Step 2: Update code that uses these colors**

Find where `platformColors[platform].bg`, `.border`, `.text` are used and simplify to just use the single class.

**Step 3: Commit**

```bash
git add frontend/calendar.html
git commit -m "fix: replace hardcoded colors with theme-aware CSS classes in calendar.html"
```

---

### Task 4: Fix workshop.html Hardcoded Colors

**Files:**
- Modify: `frontend/workshop.html`

**Step 1: Update atom type styles (around lines 619-620)**

Replace:
```javascript
insight: 'bg-blue-900/30 text-blue-400',
quote: 'bg-purple-900/30 text-purple-400',
```

With:
```javascript
insight: 'atom-insight',
quote: 'atom-quote',
```

**Step 2: Commit**

```bash
git add frontend/workshop.html
git commit -m "fix: replace hardcoded colors with theme-aware CSS classes in workshop.html"
```

---

### Task 5: Fix swipes.html Hardcoded Colors

**Files:**
- Modify: `frontend/swipes.html`

**Step 1: Update platform colors (around lines 324, 328)**

Replace:
```javascript
linkedin: 'bg-blue-900/30 text-blue-400',
```

With:
```javascript
linkedin: 'platform-linkedin',
```

Replace:
```javascript
newsletter: 'bg-purple-900/30 text-purple-400',
```

With:
```javascript
newsletter: 'platform-email',
```

**Step 2: Commit**

```bash
git add frontend/swipes.html
git commit -m "fix: replace hardcoded colors with theme-aware CSS classes in swipes.html"
```

---

### Task 6: Fix remix.html Hardcoded Colors

**Files:**
- Modify: `frontend/remix.html`

**Step 1: Update step icons (lines 158, 171)**

Replace:
```html
<span class="w-8 h-8 rounded-full bg-blue-900/30 text-blue-400 flex items-center justify-center">
```

With:
```html
<span class="w-8 h-8 rounded-full platform-linkedin flex items-center justify-center">
```

Replace:
```html
<span class="w-8 h-8 rounded-full bg-purple-900/30 text-purple-400 flex items-center justify-center">
```

With:
```html
<span class="w-8 h-8 rounded-full platform-email flex items-center justify-center">
```

**Step 2: Update border-purple-500 (line 364)**

Replace:
```html
border-l-4 border-purple-500
```

With:
```html
border-l-4" style="border-left-color: var(--platform-email-border);
```

**Step 3: Commit**

```bash
git add frontend/remix.html
git commit -m "fix: replace hardcoded colors with theme-aware CSS classes in remix.html"
```

---

## Phase 3: Accessibility Fixes

### Task 7: Add ARIA Labels to results.html

**Files:**
- Modify: `frontend/results.html`

**Step 1: Add aria-label to export menu toggle (around line 117)**

Find the export button and add:
```html
aria-label="Export options menu"
```

**Step 2: Add role="button" to export menu items (lines 124-135)**

For each `<a href="#">` in the export dropdown, add:
```html
role="button"
```

**Step 3: Commit**

```bash
git add frontend/results.html
git commit -m "a11y: add ARIA labels and roles to results.html interactive elements"
```

---

### Task 8: Add ARIA Labels to status.html

**Files:**
- Modify: `frontend/status.html`

**Step 1: Add aria-label to retry button (around line 181)**

Add to the retry button:
```html
aria-label="Retry failed job"
```

**Step 2: Commit**

```bash
git add frontend/status.html
git commit -m "a11y: add ARIA label to retry button in status.html"
```

---

## Phase 4: Backend Fixes

### Task 9: Fix Token Blacklist Check in /api/me

**Files:**
- Modify: `app/api/auth.py`

**Step 1: Import the async decode function**

At top of file, ensure this import exists:
```python
from app.services.auth import decode_access_token_async
```

If only `decode_access_token` is imported, add `decode_access_token_async`.

**Step 2: Update get_current_user to use async version (line 179)**

Replace:
```python
payload = decode_access_token(token)
```

With:
```python
payload = await decode_access_token_async(token)
```

**Step 3: Commit**

```bash
git add app/api/auth.py
git commit -m "fix: use async token validation with blacklist check in /api/me endpoint"
```

---

### Task 10: Restrict CORS Methods

**Files:**
- Modify: `app/main.py`

**Step 1: Update CORS middleware (lines 108-114)**

Replace:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

With:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
```

**Step 2: Commit**

```bash
git add app/main.py
git commit -m "security: restrict CORS to specific methods and headers"
```

---

### Task 11: Add Search String Length Validation

**Files:**
- Modify: `app/api/library.py`

**Step 1: Add validation before LIKE query (after line 35)**

Replace:
```python
if search:
    query += " AND content LIKE ?"
    params.append(f"%{search}%")
```

With:
```python
if search:
    if len(search) > 500:
        raise HTTPException(status_code=400, detail="Search string too long (max 500 characters)")
    query += " AND content LIKE ?"
    params.append(f"%{search}%")
```

**Step 2: Commit**

```bash
git add app/api/library.py
git commit -m "fix: add search string length validation to prevent DoS"
```

---

## Phase 5: Verification

### Task 12: Visual Verification

**Step 1: Start the application**

```bash
cd /Users/treynortetik/Downloads/Vibe\ Coding\ Projects/content_creation_engine
python -m uvicorn app.main:app --reload --port 5000
```

**Step 2: Test theme switching**

1. Open http://localhost:5000 in browser
2. Toggle between light and dark themes
3. Verify platform colors (LinkedIn, Email, etc.) look correct in both themes
4. Check results.html, calendar.html, workshop.html, swipes.html, remix.html

**Step 3: Test accessibility**

1. Use keyboard navigation on export menu
2. Check that ARIA labels are announced by screen reader (or inspect with dev tools)

**Step 4: Test API fixes**

1. Login and then logout
2. Try to access /api/auth/me with the old token - should fail
3. Try a search with 600+ character string - should get 400 error

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1 | Add CSS variables for platform/content colors |
| 2 | 2-6 | Replace hardcoded colors in 5 frontend files |
| 3 | 7-8 | Add ARIA labels for accessibility |
| 4 | 9-11 | Backend fixes (auth, CORS, validation) |
| 5 | 12 | Visual and functional verification |

**Total Tasks:** 12
**Estimated Time:** 45-60 minutes with subagent execution

---

## Execution Notes

- Tasks 2-6 (frontend theme fixes) can be run in parallel by separate subagents
- Tasks 9-11 (backend fixes) can be run in parallel by separate subagents
- Task 1 must complete before Tasks 2-6
- Task 12 should be run last
