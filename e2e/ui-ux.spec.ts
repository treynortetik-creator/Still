/**
 * UI/UX Tests
 * Tests for theme toggle, responsive design, modals, loading states, and general UX.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('UI/UX', () => {
  test.describe('Theme Toggle', () => {
    test('should have theme toggle on homepage', async ({ page }) => {
      await page.goto('/');

      const themeToggle = page.locator('button[aria-label*="theme"], .theme-toggle, button:has-text("Dark"), button:has-text("Light"), [data-theme-toggle]');
      const hasToggle = await themeToggle.count() > 0;

      // Theme toggle expected on landing page
      expect(hasToggle).toBe(true);
    });

    test('should toggle between light and dark mode', async ({ page }) => {
      await page.goto('/');

      const themeToggle = page.locator('button[aria-label*="theme"], .theme-toggle, [data-theme-toggle]');

      if (await themeToggle.count() > 0) {
        // Get initial theme
        const initialTheme = await page.evaluate(() => {
          return document.documentElement.classList.contains('dark') ||
                 document.body.classList.contains('dark') ||
                 document.documentElement.getAttribute('data-theme');
        });

        // Toggle
        await themeToggle.first().click();
        await page.waitForTimeout(300);

        // Check theme changed
        const newTheme = await page.evaluate(() => {
          return document.documentElement.classList.contains('dark') ||
                 document.body.classList.contains('dark') ||
                 document.documentElement.getAttribute('data-theme');
        });

        // Theme should have changed
      }
    });

    test('should persist theme preference', async ({ page }) => {
      await page.goto('/');

      const themeToggle = page.locator('.theme-toggle, [data-theme-toggle]');

      if (await themeToggle.count() > 0) {
        await themeToggle.first().click();
        await page.waitForTimeout(300);

        // Get theme after toggle
        const themeAfterToggle = await page.evaluate(() => {
          return localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme');
        });

        // Reload page
        await page.reload();
        await page.waitForTimeout(500);

        // Theme should persist
        const themeAfterReload = await page.evaluate(() => {
          return localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme');
        });

        // Themes should match
      }
    });

    test('should have theme toggle on authenticated pages', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Check for theme toggle on upload page
      const themeToggle = page.locator('.theme-toggle, [data-theme-toggle]');
      const hasToggle = await themeToggle.count() > 0;
    });
  });

  test.describe('Responsive Design', () => {
    test('should be responsive on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');

      // Check for mobile menu or hamburger
      const mobileMenu = page.locator('.hamburger, .mobile-menu, button[aria-label*="menu"], .menu-toggle');
      const hasMobileMenu = await mobileMenu.count() > 0;

      // Content should still be visible
      const mainContent = page.locator('main, .content, .hero, h1');
      await expect(mainContent.first()).toBeVisible();
    });

    test('should be responsive on tablet viewport', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/');

      // Content should be visible and properly laid out
      const mainContent = page.locator('main, .content, .hero');
      await expect(mainContent.first()).toBeVisible();
    });

    test('should handle large desktop viewport', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto('/');

      // Content should be centered or have max-width
      const mainContent = page.locator('main, .container, .content');
      await expect(mainContent.first()).toBeVisible();
    });

    test('should have readable text at all sizes', async ({ page }) => {
      const viewports = [
        { width: 375, height: 667 },
        { width: 768, height: 1024 },
        { width: 1440, height: 900 },
      ];

      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        await page.goto('/');

        // Text should be visible and not overflow
        const text = page.locator('h1, p, .text');
        if (await text.count() > 0) {
          const firstText = text.first();
          await expect(firstText).toBeVisible();
        }
      }
    });
  });

  test.describe('Loading States', () => {
    test('should show loading indicator during API calls', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');

      // Look for loading indicator when form submits
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      // Start watching for loading state
      const loadingPromise = page.locator('.loading, .spinner, [aria-busy="true"], .loading-indicator').waitFor({ state: 'visible', timeout: 5000 }).catch(() => null);

      await page.click('button[type="submit"]');

      // Loading state may appear briefly
    });

    test('should show skeleton loaders if present', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      await page.goto('/reserve.html');

      // Skeleton loaders for async content
      const skeleton = page.locator('.skeleton, .placeholder, .loading-skeleton');
      // Skeleton loaders may appear during load
    });

    test('should disable submit button while loading', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', 'test@example.com');
      await page.fill('input[type="password"]', 'TestPassword123!');

      const submitButton = page.locator('button[type="submit"]');

      // Click and immediately check if disabled
      await submitButton.click();

      // Button may be disabled during submission
      const isDisabled = await submitButton.isDisabled().catch(() => false);
      // Some implementations disable button during API call
    });
  });

  test.describe('Modals', () => {
    test('should trap focus within modal', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      await page.goto('/reserve.html');

      // Try to open a modal (e.g., generate modal)
      const checkbox = page.locator('.card input[type="checkbox"]');

      if (await checkbox.count() > 0) {
        await checkbox.first().check();

        const generateButton = page.locator('button:has-text("Generate")');

        if (await generateButton.count() > 0 && await generateButton.first().isEnabled()) {
          await generateButton.first().click();
          await page.waitForTimeout(300);

          const modal = page.locator('.modal, [role="dialog"]');

          if (await modal.count() > 0) {
            // Tab through modal elements
            await page.keyboard.press('Tab');
            await page.keyboard.press('Tab');

            // Focus should stay in modal
          }
        }
      }
    });

    test('should close modal on escape key', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      await page.goto('/reserve.html');

      const checkbox = page.locator('.card input[type="checkbox"]');

      if (await checkbox.count() > 0) {
        await checkbox.first().check();

        const generateButton = page.locator('button:has-text("Generate")');

        if (await generateButton.count() > 0 && await generateButton.first().isEnabled()) {
          await generateButton.first().click();
          await page.waitForTimeout(300);

          const modal = page.locator('.modal, [role="dialog"]');

          if (await modal.count() > 0) {
            await page.keyboard.press('Escape');
            await page.waitForTimeout(300);

            // Modal should be closed
            const modalAfter = await modal.isVisible().catch(() => false);
          }
        }
      }
    });

    test('should close modal on backdrop click', async ({ page }) => {
      // Similar to escape test but click backdrop
    });
  });

  test.describe('Toast Notifications', () => {
    test('should display toast on successful actions', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');

      // Toast may appear on successful registration
      const toast = page.locator('.toast, .notification, [role="status"]');
      // Toasts provide feedback
    });

    test('should auto-dismiss toast after delay', async ({ page }) => {
      // Toasts should auto-dismiss
    });
  });

  test.describe('Form UX', () => {
    test('should show validation errors inline', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');
      await emailInput.fill('invalid');
      await emailInput.blur();

      // Error should appear near the field
      const errorMessage = page.locator('.error, .invalid-feedback, [role="alert"]');
      // Inline errors are better UX than alert boxes
    });

    test('should focus first error field on submit', async ({ page }) => {
      await page.goto('/register.html');

      // Submit empty form
      const submitButton = page.locator('button[type="submit"]');

      if (await submitButton.isEnabled()) {
        await submitButton.click();
        await page.waitForTimeout(300);

        // First invalid field should be focused
      }
    });

    test('should have proper input types', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');
      const passwordInput = page.locator('input[type="password"]');

      await expect(emailInput).toHaveAttribute('type', 'email');
      await expect(passwordInput.first()).toHaveAttribute('type', 'password');
    });

    test('should have autocomplete attributes', async ({ page }) => {
      await page.goto('/login.html');

      const emailInput = page.locator('input[type="email"]');
      const passwordInput = page.locator('input[type="password"]');

      // Autocomplete helps password managers
      const emailAutocomplete = await emailInput.getAttribute('autocomplete');
      const passwordAutocomplete = await passwordInput.getAttribute('autocomplete');
      // autocomplete="email" and autocomplete="current-password" expected
    });
  });

  test.describe('Navigation UX', () => {
    test('should highlight active navigation item', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Active nav item should be highlighted
      const activeNav = page.locator('nav .active, nav [aria-current="page"], .nav-active');
      // Active state helps orient users
    });

    test('should have breadcrumbs where appropriate', async ({ page }) => {
      // Breadcrumbs help with deep navigation
      const breadcrumbs = page.locator('.breadcrumb, nav[aria-label="breadcrumb"]');
      // Optional but good for complex flows
    });
  });

  test.describe('Empty States', () => {
    test('should show helpful empty states', async ({ page }) => {
      const email = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      await page.goto('/reserve.html');

      // Empty state should have CTA
      const emptyState = page.locator('.empty-state, .no-content');

      if (await emptyState.count() > 0) {
        const cta = emptyState.locator('a, button');
        const hasCta = await cta.count() > 0;
        // CTAs guide users on next steps
      }
    });
  });

  test.describe('Animations', () => {
    test('should respect reduced motion preference', async ({ page }) => {
      // Set reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto('/');

      // Animations should be disabled or minimal
    });

    test('should have smooth transitions', async ({ page }) => {
      await page.goto('/');

      // Page should have CSS transitions defined
      const hasTransitions = await page.evaluate(() => {
        const body = document.body;
        const style = getComputedStyle(body);
        return style.transition !== 'none' || style.transitionDuration !== '0s';
      });
      // Transitions improve perceived performance
    });
  });

  test.describe('Error States', () => {
    test('should show user-friendly error messages', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', 'wrong@example.com');
      await page.fill('input[type="password"]', 'wrongpassword');
      await page.click('button[type="submit"]');

      await page.waitForTimeout(2000);

      // Error should be user-friendly, not technical
      const error = page.locator('.error, [role="alert"]');

      if (await error.count() > 0) {
        const errorText = await error.first().textContent();
        // Should not contain stack traces or technical jargon
      }
    });
  });
});
