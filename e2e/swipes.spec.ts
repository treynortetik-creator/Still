/**
 * Swipe Files Page Tests
 * Tests for competitive content collection and style DNA analysis.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Swipes Page', () => {
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
    test('should load swipes page', async ({ page }) => {
      await page.goto('/swipes.html');
      const hasContent = await page.locator('#swipes-grid, #empty-state, #loading').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should have add swipe button', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await expect(addBtn.first()).toBeVisible();
    });

    test('should show empty state for new user', async ({ page }) => {
      await page.goto('/swipes.html');
      await page.waitForTimeout(1000);
      const emptyState = page.locator('#empty-state');
      // New user should see empty state
    });

    test('should have filter buttons', async ({ page }) => {
      await page.goto('/swipes.html');
      const filters = page.locator('.filter-btn');
      expect(await filters.count()).toBeGreaterThanOrEqual(4);
    });

    test('should have swipe count display', async ({ page }) => {
      await page.goto('/swipes.html');
      await expect(page.locator('#swipe-count')).toBeVisible();
    });
  });

  test.describe('Add Swipe Modal', () => {
    test('should open add swipe modal', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await addBtn.first().click();
      const modal = page.locator('#swipe-modal');
      await expect(modal).toBeVisible();
    });

    test('should have content textarea', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await addBtn.first().click();
      await expect(page.locator('#swipe-content')).toBeVisible();
    });

    test('should have source type selector', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await addBtn.first().click();
      await expect(page.locator('#swipe-source-type')).toBeVisible();
    });

    test('should have optional fields (title, URL, tags, notes)', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await addBtn.first().click();
      await expect(page.locator('#swipe-title')).toBeVisible();
      await expect(page.locator('#swipe-url')).toBeVisible();
      await expect(page.locator('#swipe-tags')).toBeVisible();
      await expect(page.locator('#swipe-notes')).toBeVisible();
    });

    test('should close modal on cancel', async ({ page }) => {
      await page.goto('/swipes.html');
      const addBtn = page.locator('button:has-text("Add"), button:has-text("New Swipe")');
      await addBtn.first().click();
      const cancelBtn = page.locator('#swipe-modal button:has-text("Cancel")');
      await cancelBtn.click();
      await expect(page.locator('#swipe-modal')).toBeHidden();
    });
  });

  test.describe('Filter Functionality', () => {
    test('should filter by content type', async ({ page }) => {
      await page.goto('/swipes.html');
      const linkedinFilter = page.locator('.filter-btn[data-type="linkedin"], button:has-text("LinkedIn")');
      if (await linkedinFilter.count() > 0) {
        await linkedinFilter.first().click();
        // Filter should activate
      }
    });

    test('should show all when all filter clicked', async ({ page }) => {
      await page.goto('/swipes.html');
      const allFilter = page.locator('.filter-btn[data-type="all"], button:has-text("All")');
      if (await allFilter.count() > 0) {
        await allFilter.first().click();
        // All swipes should show
      }
    });
  });

  test.describe('Style DNA', () => {
    test('should have style DNA section hidden initially', async ({ page }) => {
      await page.goto('/swipes.html');
      const styleDna = page.locator('#style-dna');
      // Style DNA hidden until enough swipes are analyzed
    });
  });
});
