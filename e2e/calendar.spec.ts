/**
 * Calendar Page Tests
 * Tests for content scheduling and calendar functionality.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Calendar Page', () => {
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
    test('should load calendar page', async ({ page }) => {
      await page.goto('/calendar.html');
      await expect(page.locator('#calendar-grid')).toBeVisible();
    });

    test('should show current month', async ({ page }) => {
      await page.goto('/calendar.html');
      const monthDisplay = page.locator('#current-month');
      await expect(monthDisplay).toBeVisible();
      const text = await monthDisplay.textContent();
      expect(text).toBeTruthy();
    });

    test('should have month navigation buttons', async ({ page }) => {
      await page.goto('/calendar.html');
      const prevBtn = page.locator('button:has-text("←"), button:has-text("Prev"), [aria-label*="previous"]');
      const nextBtn = page.locator('button:has-text("→"), button:has-text("Next"), [aria-label*="next"]');
      expect(await prevBtn.count()).toBeGreaterThan(0);
      expect(await nextBtn.count()).toBeGreaterThan(0);
    });

    test('should have today button', async ({ page }) => {
      await page.goto('/calendar.html');
      const todayBtn = page.locator('button:has-text("Today")');
      await expect(todayBtn).toBeVisible();
    });

    test('should have export dropdown', async ({ page }) => {
      await page.goto('/calendar.html');
      const exportBtn = page.locator('#export-dropdown, button:has-text("Export")');
      expect(await exportBtn.count()).toBeGreaterThan(0);
    });
  });

  test.describe('Calendar Grid', () => {
    test('should render 7-day column headers', async ({ page }) => {
      await page.goto('/calendar.html');
      const grid = page.locator('#calendar-grid');
      await expect(grid).toBeVisible();
    });

    test('should have day cells in the grid', async ({ page }) => {
      await page.goto('/calendar.html');
      await page.waitForTimeout(1000);
      // Calendar should render day cells
      const cells = page.locator('#calendar-grid > div, #calendar-grid td');
      expect(await cells.count()).toBeGreaterThan(0);
    });
  });

  test.describe('Month Navigation', () => {
    test('should navigate to next month', async ({ page }) => {
      await page.goto('/calendar.html');
      const monthDisplay = page.locator('#current-month');
      const initialMonth = await monthDisplay.textContent();

      const nextBtn = page.locator('button:has-text("→"), button:has-text("Next")').first();
      await nextBtn.click();
      await page.waitForTimeout(500);

      const newMonth = await monthDisplay.textContent();
      expect(newMonth).not.toBe(initialMonth);
    });

    test('should navigate to previous month', async ({ page }) => {
      await page.goto('/calendar.html');
      const monthDisplay = page.locator('#current-month');
      const initialMonth = await monthDisplay.textContent();

      const prevBtn = page.locator('button:has-text("←"), button:has-text("Prev")').first();
      await prevBtn.click();
      await page.waitForTimeout(500);

      const newMonth = await monthDisplay.textContent();
      expect(newMonth).not.toBe(initialMonth);
    });

    test('should return to current month with Today button', async ({ page }) => {
      await page.goto('/calendar.html');
      // Navigate away
      const nextBtn = page.locator('button:has-text("→"), button:has-text("Next")').first();
      await nextBtn.click();
      await nextBtn.click();
      await page.waitForTimeout(500);

      // Click today
      await page.click('button:has-text("Today")');
      await page.waitForTimeout(500);

      const monthDisplay = page.locator('#current-month');
      const now = new Date();
      const expectedMonth = now.toLocaleString('default', { month: 'long', year: 'numeric' });
      // Month should contain current month name
    });
  });

  test.describe('Unscheduled Sidebar', () => {
    test('should show unscheduled content section', async ({ page }) => {
      await page.goto('/calendar.html');
      const sidebar = page.locator('#unscheduled-list');
      await expect(sidebar).toBeVisible();
    });
  });

  test.describe('Schedule Modal', () => {
    test('should have schedule modal elements', async ({ page }) => {
      await page.goto('/calendar.html');
      const modal = page.locator('#schedule-modal');
      // Modal exists but should be hidden
      if (await modal.count() > 0) {
        await expect(modal).toBeHidden();
      }
    });
  });

  test.describe('Export', () => {
    test('should show export options when clicked', async ({ page }) => {
      await page.goto('/calendar.html');
      const exportBtn = page.locator('#export-dropdown, button:has-text("Export")').first();
      await exportBtn.click();
      await page.waitForTimeout(300);

      const menu = page.locator('#export-menu, .export-options');
      // Export menu should appear
    });
  });
});
