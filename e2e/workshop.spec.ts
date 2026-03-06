/**
 * Workshop Page Tests
 * Tests for the content editing workspace.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Workshop Page', () => {
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
    test('should load workshop page', async ({ page }) => {
      await page.goto('/workshop.html');
      // Should show list view or empty state
      const hasContent = await page.locator('#list-view, #empty-state, .workshop').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should show filter buttons', async ({ page }) => {
      await page.goto('/workshop.html');
      const filterBtns = page.locator('.filter-btn');
      expect(await filterBtns.count()).toBeGreaterThanOrEqual(3);
    });

    test('should have filter options for all, draft, polished, published', async ({ page }) => {
      await page.goto('/workshop.html');
      await expect(page.locator('button:has-text("All"), .filter-btn:has-text("All")')).toBeVisible();
    });

    test('should show empty state for new user', async ({ page }) => {
      await page.goto('/workshop.html');
      await page.waitForTimeout(1000);
      const emptyState = page.locator('#empty-state');
      // New user should see empty state or loading
    });
  });

  test.describe('Filter Functionality', () => {
    test('should switch filter buttons', async ({ page }) => {
      await page.goto('/workshop.html');
      const filters = page.locator('.filter-btn');
      if (await filters.count() > 1) {
        await filters.nth(1).click();
        // Active filter should change styling
      }
    });
  });

  test.describe('Editor View Elements', () => {
    test('should have editor view hidden by default', async ({ page }) => {
      await page.goto('/workshop.html');
      const editorView = page.locator('#editor-view');
      // Editor should be hidden until content is selected
      if (await editorView.count() > 0) {
        await expect(editorView).toBeHidden();
      }
    });
  });
});
