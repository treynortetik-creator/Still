/**
 * Theme Manager for Still
 * Handles light/dark mode with localStorage persistence and system preference detection
 */

const ThemeManager = {
    STORAGE_KEY: 'still-theme',
    THEMES: {
        LIGHT: 'light',
        DARK: 'dark'
    },

    /**
     * Initialize theme on page load
     * Call this early (in <head>) to prevent flash of wrong theme
     */
    init() {
        const theme = this.getTheme();
        this.applyTheme(theme);

        // Listen for system preference changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                // Only auto-switch if user hasn't set a preference
                if (!localStorage.getItem(this.STORAGE_KEY)) {
                    this.applyTheme(e.matches ? this.THEMES.DARK : this.THEMES.LIGHT);
                }
            });
        }
    },

    /**
     * Get the current theme from localStorage or system preference
     */
    getTheme() {
        // Check localStorage first
        const stored = localStorage.getItem(this.STORAGE_KEY);
        if (stored && (stored === this.THEMES.LIGHT || stored === this.THEMES.DARK)) {
            return stored;
        }

        // Fall back to system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            return this.THEMES.LIGHT;
        }

        // Default to dark (matches current design)
        return this.THEMES.DARK;
    },

    /**
     * Apply a theme to the document
     */
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);

        // Update toggle button icons if they exist
        this.updateToggleIcons(theme);
    },

    /**
     * Toggle between light and dark themes
     */
    toggle() {
        const current = this.getTheme();
        const newTheme = current === this.THEMES.DARK ? this.THEMES.LIGHT : this.THEMES.DARK;

        localStorage.setItem(this.STORAGE_KEY, newTheme);
        this.applyTheme(newTheme);

        return newTheme;
    },

    /**
     * Set a specific theme
     */
    setTheme(theme) {
        if (theme === this.THEMES.LIGHT || theme === this.THEMES.DARK) {
            localStorage.setItem(this.STORAGE_KEY, theme);
            this.applyTheme(theme);
        }
    },

    /**
     * Update toggle button icons based on current theme
     */
    updateToggleIcons(theme) {
        const sunIcons = document.querySelectorAll('.theme-icon-sun');
        const moonIcons = document.querySelectorAll('.theme-icon-moon');

        if (theme === this.THEMES.LIGHT) {
            // In light mode: show moon (click to go dark)
            sunIcons.forEach(icon => icon.classList.add('hidden'));
            moonIcons.forEach(icon => icon.classList.remove('hidden'));
        } else {
            // In dark mode: show sun (click to go light)
            sunIcons.forEach(icon => icon.classList.remove('hidden'));
            moonIcons.forEach(icon => icon.classList.add('hidden'));
        }
    },

    /**
     * Check if current theme is light
     */
    isLight() {
        return this.getTheme() === this.THEMES.LIGHT;
    },

    /**
     * Check if current theme is dark
     */
    isDark() {
        return this.getTheme() === this.THEMES.DARK;
    }
};

// Initialize theme immediately to prevent flash
ThemeManager.init();

// Also run on DOMContentLoaded to update toggle icons
document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.updateToggleIcons(ThemeManager.getTheme());
});
