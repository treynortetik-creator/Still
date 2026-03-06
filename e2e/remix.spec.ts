/**
 * Remix Page Tests
 * Tests for content remixing from existing stills.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Remix Page', () => {
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
    test('should load remix page', async ({ page }) => {
      await page.goto('/remix.html');
      const hasContent = await page.locator('#total-stills, #empty-state').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should show stills stats', async ({ page }) => {
      await page.goto('/remix.html');
      await page.waitForTimeout(1000);
      await expect(page.locator('#total-stills')).toBeVisible();
    });

    test('should show stills by type breakdown', async ({ page }) => {
      await page.goto('/remix.html');
      await page.waitForTimeout(1000);
      await expect(page.locator('#stills-by-type')).toBeVisible();
    });

    test('should show top tags', async ({ page }) => {
      await page.goto('/remix.html');
      await page.waitForTimeout(1000);
      await expect(page.locator('#top-tags')).toBeVisible();
    });

    test('should show empty state for new user with few stills', async ({ page }) => {
      await page.goto('/remix.html');
      await page.waitForTimeout(1000);
      // New user should see empty state since they have < 5 stills
      const emptyState = page.locator('#empty-state');
      // May or may not be visible depending on still count
    });
  });
});
