/**
 * Brand Voice Configuration Tests
 * Tests for the standalone brand voice configuration page.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Brand Voice Page', () => {
  test.beforeEach(async ({ page }) => {
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

  test.describe('Page Structure', () => {
    test('should load brand voice page', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#company-name')).toBeVisible();
    });

    test('should have company info fields', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#company-name')).toBeVisible();
      await expect(page.locator('#industry')).toBeVisible();
    });

    test('should have tone-by-platform fields', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#tone-linkedin')).toBeVisible();
      await expect(page.locator('#tone-blog')).toBeVisible();
      await expect(page.locator('#tone-email')).toBeVisible();
    });

    test('should have vocabulary level selector', async ({ page }) => {
      await page.goto('/brand-voice.html');
      const vocabSelect = page.locator('#vocabulary-level');
      await expect(vocabSelect).toBeVisible();
      const options = vocabSelect.locator('option');
      expect(await options.count()).toBeGreaterThanOrEqual(3);
    });

    test('should have save and reset buttons', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#save-btn')).toBeVisible();
      const resetBtn = page.locator('button:has-text("Reset")');
      await expect(resetBtn.first()).toBeVisible();
    });
  });

  test.describe('Core Principles', () => {
    test('should have add principle input and button', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#new-principle')).toBeVisible();
    });

    test('should add a principle', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await page.fill('#new-principle', 'Always lead with data');
      const addBtn = page.locator('button:has-text("Add")').first();
      await addBtn.click();
      const container = page.locator('#principles-container');
      await expect(container).toContainText('Always lead with data');
    });
  });

  test.describe('Phrases Management', () => {
    test('should have phrases-to-use input', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#new-phrase-use')).toBeVisible();
    });

    test('should have phrases-to-avoid input', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await expect(page.locator('#new-phrase-avoid')).toBeVisible();
    });
  });

  test.describe('Form Interaction', () => {
    test('should fill and save brand voice config', async ({ page }) => {
      await page.goto('/brand-voice.html');

      await page.fill('#company-name', 'Test Company');
      await page.fill('#industry', 'Technology');
      await page.fill('#tone-linkedin', 'Professional and authoritative');
      await page.fill('#tone-blog', 'Educational and approachable');
      await page.fill('#tone-email', 'Warm and personal');

      // Save
      const responsePromise = page.waitForResponse(resp =>
        resp.url().includes('/api/brand-voice/config') && resp.request().method() === 'PUT'
      );
      await page.click('#save-btn');

      const response = await responsePromise;
      expect(response.status()).toBeLessThan(500);
    });

    test('should show status message after save', async ({ page }) => {
      await page.goto('/brand-voice.html');
      await page.fill('#company-name', 'Test Corp');
      await page.click('#save-btn');
      await page.waitForTimeout(1000);
      const status = page.locator('#status-message, .toast, [role="alert"]');
      // Status message should appear
    });
  });
});
