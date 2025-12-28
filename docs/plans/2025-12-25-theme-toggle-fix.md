# Theme Toggle Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a consistent theme toggle button to the top-right of all pages (frontend and admin), fix admin panel light mode contrast issues, and rename "ContentMultiplier" to "Still" in the admin sidebar.

**Architecture:** The theme system already exists (ThemeManager in theme.js with CSS variables). Frontend pages already have toggles in the navbar. Admin pages need: (1) a toggle in the top-right content area, (2) replacement of hardcoded `bg-white` and `text-gray-*` classes with CSS variable classes.

**Tech Stack:** HTML, Tailwind CSS, CSS variables, Jinja2 templates

---

## Task 1: Update Admin Base Template - Add Top-Right Toggle and Rename to "Still"

**Files:**
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/base.html`

**Step 1: Add theme toggle to main content header**

In base.html, modify the main content area (line 152-155) to include a header with theme toggle:

Replace:
```html
        <!-- Main Content -->
        <div class="ml-64 flex-1 p-8">
            {% block content %}{% endblock %}
        </div>
```

With:
```html
        <!-- Main Content -->
        <div class="ml-64 flex-1">
            <!-- Top Header with Theme Toggle -->
            <div class="flex justify-end items-center px-8 py-4 border-b" style="border-color: var(--admin-border);">
                <button onclick="ThemeManager.toggle()" class="theme-toggle" title="Toggle light/dark mode">
                    <svg class="theme-icon-sun w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                    <svg class="theme-icon-moon hidden w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                    </svg>
                </button>
            </div>
            <div class="p-8">
                {% block content %}{% endblock %}
            </div>
        </div>
```

**Step 2: Rename "ContentMultiplier" to "Still" in sidebar**

Replace the sidebar header (lines 65-68):
```html
            <div class="p-4">
                <a href="/" class="text-xl font-bold text-white">ContentMultiplier</a>
                <span class="text-gray-400 text-sm block">Admin Panel</span>
            </div>
```

With:
```html
            <div class="p-4">
                <a href="/" class="text-xl font-bold text-white">Still</a>
                <span class="text-gray-400 text-sm block">Admin Panel</span>
            </div>
```

**Step 3: Remove old sidebar toggle button**

Remove lines 137-148 (the old theme toggle in sidebar navigation).

**Step 4: Add theme-toggle CSS to admin**

Add to the `<style>` block (after line 52):
```css
.theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: transparent;
    border: 1px solid var(--admin-border);
    color: var(--admin-text-muted);
    cursor: pointer;
    transition: all 0.2s ease;
}
.theme-toggle:hover {
    background: var(--admin-border);
    color: var(--admin-text);
}
```

---

## Task 2: Fix Admin Dashboard Light Mode Styling

**Files:**
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/dashboard.html`

**Step 1: Replace hardcoded bg-white with admin-card class**

Replace all `bg-white` with `admin-card`:
- Line 11, 16, 21, 26: `<div class="bg-white rounded-lg shadow p-6">` → `<div class="admin-card rounded-lg shadow p-6 border">`
- Line 34, 52: `<div class="bg-white rounded-lg shadow p-6">` → `<div class="admin-card rounded-lg shadow p-6 border">`
- Line 66: `<div class="bg-white rounded-lg shadow">` → `<div class="admin-card rounded-lg shadow border">`

**Step 2: Replace hardcoded text-gray-* colors**

Replace:
- `text-gray-500` → `style="color: var(--admin-text-muted);"`
- `text-gray-600` → `style="color: var(--admin-text-muted);"`
- `border-gray-300` → `style="border-color: var(--admin-border);"`
- `hover:bg-gray-50` → `hover:opacity-80`

**Step 3: Fix dynamic JavaScript content**

In the script section, update the activity rendering (line 97-109) to use CSS variables.

---

## Task 3: Fix Admin Settings Light Mode Styling

**Files:**
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/settings.html`

**Step 1: Replace hardcoded colors**

Replace all:
- `bg-white` → `admin-card` + `border`
- `text-gray-*` → inline style with `var(--admin-text)` or `var(--admin-text-muted)`
- `border-gray-*` → inline style with `var(--admin-border)`
- `bg-gray-200` → inline style with `var(--admin-border)`

---

## Task 4: Fix Admin Prompt Editor Light Mode Styling

**Files:**
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/prompt_editor.html`

**Step 1: Replace hardcoded colors**

Same pattern as above - replace `bg-white`, `text-gray-*`, `border-gray-*` with admin CSS variable classes.

---

## Task 5: Fix Remaining Admin Templates

**Files:**
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/client_view.html`
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/library_browser.html`
- Modify: `/Users/treynortetik/Downloads/Vibe Coding Projects/content_creation_engine/app/templates/admin/error_logs.html`

Apply same pattern to all remaining admin templates.

---

## Task 6: Verify Frontend Pages Have Theme Toggle

**Files:**
- Check all 18 frontend HTML pages to verify they have the theme toggle

The frontend pages (index.html, upload.html, settings.html, etc.) already have theme toggles in the navbar. No changes needed unless any are missing.

---

## Summary of Changes

| File | Changes |
|------|---------|
| admin/base.html | Add top-right toggle, rename to "Still", remove sidebar toggle, add CSS |
| admin/dashboard.html | Replace bg-white, text-gray-* with CSS variable classes |
| admin/settings.html | Replace hardcoded colors with CSS variable classes |
| admin/prompt_editor.html | Replace hardcoded colors with CSS variable classes |
| admin/client_view.html | Replace hardcoded colors with CSS variable classes |
| admin/library_browser.html | Replace hardcoded colors with CSS variable classes |
| admin/error_logs.html | Replace hardcoded colors with CSS variable classes |

---

## Testing

After implementation:
1. Toggle theme on frontend pages - verify consistent button placement
2. Toggle theme on admin pages - verify button is top-right
3. In light mode on admin pages - verify all text is readable (dark text on light background)
4. Verify sidebar still shows "Still Admin Panel"
5. Check all admin pages load without errors
