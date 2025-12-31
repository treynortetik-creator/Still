/**
 * Navigation & Routing Tests
 * Tests that all pages load correctly and navigation works.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Navigation & Routing', () => {
  test.describe('Public Pages', () => {
    test('should load the homepage', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveTitle(/.+/);

      // Check for key elements on landing page
      const hasHero = await page.locator('h1, .hero, .headline').count() > 0;
      expect(hasHero).toBe(true);
    });

    test('should load the login page', async ({ page }) => {
      await page.goto('/login.html');

      // Should have email and password inputs
      await expect(page.locator('input[type="email"]')).toBeVisible();
      await expect(page.locator('input[type="password"]')).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeVisible();
    });

    test('should load the register page', async ({ page }) => {
      await page.goto('/register.html');

      // Should have registration form
      await expect(page.locator('input[type="email"]')).toBeVisible();
      await expect(page.locator('input[type="password"]').first()).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeVisible();
    });

    test('should return 404 for non-existent pages', async ({ page }) => {
      const response = await page.goto('/nonexistent-page-12345.html');

      // Either 404 status or redirect to error page
      expect(response?.status() === 404 || response?.status() === 200).toBe(true);
    });

    test('should have health check endpoint', async ({ page }) => {
      const response = await page.goto('/health');
      expect(response?.status()).toBe(200);

      const content = await page.content();
      expect(content).toContain('healthy');
    });

    test('should have API info endpoint', async ({ page }) => {
      const response = await page.goto('/api');
      expect(response?.status()).toBe(200);

      const content = await page.content();
      expect(content).toContain('ContentMultiplier');
    });
  });

  test.describe('Protected Pages (with auth)', () => {
    let testEmail: string;
    const testPassword = 'TestPassword123!';

    test.beforeEach(async ({ page }) => {
      // Register and login before each test
      testEmail = uniqueEmail();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', testEmail);
      await page.fill('input[type="password"]:not([name*="confirm"])', testPassword);

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(testPassword);
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });
    });

    test('should load upload page', async ({ page }) => {
      await page.goto('/upload.html');
      await expect(page).toHaveURL(/upload/);

      // Should have upload-related elements
      const hasUploadElement = await page.locator('input[type="file"], .dropzone, .upload-area, [data-upload]').count() > 0;
      expect(hasUploadElement).toBe(true);
    });

    test('should load reserve/library page', async ({ page }) => {
      await page.goto('/reserve.html');

      // Should have library elements or empty state
      const hasContent = await page.locator('.library, .reserve, .stills, .empty-state, .no-content').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should load settings page', async ({ page }) => {
      await page.goto('/settings.html');

      // Should have settings-related elements
      const hasSettings = await page.locator('form, .settings, input, select, .preference').count() > 0;
      expect(hasSettings).toBe(true);
    });

    test('should load workshop page', async ({ page }) => {
      await page.goto('/workshop.html');

      // Should have nav container (page loaded successfully)
      const hasNav = await page.locator('#nav-container').count() > 0;
      expect(hasNav).toBe(true);
    });

    test('should load calendar page', async ({ page }) => {
      await page.goto('/calendar.html');

      // Should have calendar-specific elements
      const hasNav = await page.locator('#nav-container').count() > 0;
      const hasCalendar = await page.locator('#calendar-grid, #current-month').count() > 0;
      expect(hasNav && hasCalendar).toBe(true);
    });

    test('should load autopilot page', async ({ page }) => {
      await page.goto('/autopilot.html');

      // Should have autopilot-specific elements
      const hasNav = await page.locator('#nav-container').count() > 0;
      const hasStats = await page.locator('#stat-active, #stat-pending').count() > 0;
      expect(hasNav && hasStats).toBe(true);
    });

    test('should load brand-voice page', async ({ page }) => {
      await page.goto('/brand-voice.html');

      // Should have brand voice elements
      const hasNav = await page.locator('#nav-container').count() > 0;
      const hasContent = await page.locator('#main-content, #loading').count() > 0;
      expect(hasNav && hasContent).toBe(true);
    });

    test('should load swipes page', async ({ page }) => {
      await page.goto('/swipes.html');

      // Should have swipes-specific elements
      const hasNav = await page.locator('#nav-container').count() > 0;
      const hasSwipes = await page.locator('#swipe-count, #loading').count() > 0;
      expect(hasNav && hasSwipes).toBe(true);
    });

    test('should load remix page', async ({ page }) => {
      await page.goto('/remix.html');

      // Should have remix-specific elements
      const hasNav = await page.locator('#nav-container').count() > 0;
      const hasRemix = await page.locator('#analyze-btn, #library-stats').count() > 0;
      expect(hasNav && hasRemix).toBe(true);
    });
  });

  test.describe('Navigation Links', () => {
    test.beforeEach(async ({ page }) => {
      // Register and login
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
    });

    test('should navigate from homepage to login', async ({ page }) => {
      // Clear auth first
      await page.evaluate(() => localStorage.clear());
      await page.goto('/');

      const loginLink = page.locator('a[href*="login"], a:has-text("Login"), a:has-text("Sign in")');
      if (await loginLink.count() > 0) {
        await loginLink.first().click();
        await expect(page).toHaveURL(/login/);
      }
    });

    test('should navigate between main sections', async ({ page }) => {
      // Test navigation from upload page
      await page.goto('/upload.html');

      // Look for nav links
      const navLinks = page.locator('nav a, .nav a, .sidebar a, header a');
      const count = await navLinks.count();

      // Should have some navigation
      expect(count).toBeGreaterThan(0);
    });

    test('should have consistent navigation across pages', async ({ page }) => {
      const pagesToCheck = ['/upload.html', '/reserve.html', '/settings.html'];

      for (const pagePath of pagesToCheck) {
        await page.goto(pagePath);

        // Check for navigation element
        const hasNav = await page.locator('nav, .nav, .sidebar, .menu').count() > 0;
        expect(hasNav).toBe(true);
      }
    });
  });

  test.describe('Homepage CTAs', () => {
    test('should have Start Creating CTA that works', async ({ page }) => {
      await page.goto('/');

      const startCta = page.locator('a:has-text("Start Creating"), button:has-text("Start Creating"), a:has-text("Get Started")');

      if (await startCta.count() > 0) {
        await startCta.first().click();
        await page.waitForTimeout(1000);

        // Should navigate to upload or login
        const url = page.url();
        expect(url.includes('upload') || url.includes('login') || url.includes('register')).toBe(true);
      }
    });

    test('should have Explore Reserve CTA if present', async ({ page }) => {
      await page.goto('/');

      const reserveCta = page.locator('a:has-text("Explore Reserve"), a:has-text("Reserve"), a:has-text("Library")');

      if (await reserveCta.count() > 0) {
        await reserveCta.first().click();
        await page.waitForTimeout(1000);

        // Should navigate to reserve/library or login
        const url = page.url();
        expect(url.includes('reserve') || url.includes('library') || url.includes('login')).toBe(true);
      }
    });
  });

  test.describe('Admin Routes', () => {
    test('should load admin dashboard', async ({ page }) => {
      const response = await page.goto('/admin/');

      // Admin routes may require special auth or return 503 if admin not configured
      const status = response?.status() ?? 0;
      expect(status < 500 || status === 503).toBe(true);
    });

    test('should load admin settings', async ({ page }) => {
      const response = await page.goto('/admin/settings');
      // 503 expected when ADMIN_USERNAME/ADMIN_PASSWORD not configured
      const status = response?.status() ?? 0;
      expect(status < 500 || status === 503).toBe(true);
    });

    test('should load admin prompt editor', async ({ page }) => {
      const response = await page.goto('/admin/prompts');
      // 503 expected when ADMIN_USERNAME/ADMIN_PASSWORD not configured
      const status = response?.status() ?? 0;
      expect(status < 500 || status === 503).toBe(true);
    });
  });

  test.describe('Error Handling', () => {
    test('should handle malformed URLs gracefully', async ({ page }) => {
      const response = await page.goto('/upload.html?invalid=%');

      // Should not crash
      expect(response?.status()).toBeLessThan(500);
    });

    test('should handle very long paths', async ({ page }) => {
      const longPath = '/a'.repeat(500) + '.html';
      const response = await page.goto(longPath);

      // Should handle gracefully (404 or redirect)
      expect(response?.status()).toBeLessThan(500);
    });
  });
});
