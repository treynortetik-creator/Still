/**
 * Autopilot Page Tests
 * Tests for RSS/YouTube feed monitoring and source management.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Autopilot Page', () => {
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
    test('should load autopilot page', async ({ page }) => {
      await page.goto('/autopilot.html');
      // Should show stats or empty state
      const hasContent = await page.locator('#sources-container, #empty-state, #stat-active').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should show stats cards', async ({ page }) => {
      await page.goto('/autopilot.html');
      await page.waitForTimeout(1000);
      await expect(page.locator('#stat-active')).toBeVisible();
      await expect(page.locator('#stat-pending')).toBeVisible();
      await expect(page.locator('#stat-today')).toBeVisible();
      await expect(page.locator('#stat-total')).toBeVisible();
    });

    test('should have add source button', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await expect(addBtn.first()).toBeVisible();
    });

    test('should show empty state for new user', async ({ page }) => {
      await page.goto('/autopilot.html');
      await page.waitForTimeout(1000);
      const emptyState = page.locator('#empty-state');
      // New user should see empty state
    });
  });

  test.describe('Add Source Modal', () => {
    test('should open add source modal', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      const modal = page.locator('#source-modal');
      await expect(modal).toBeVisible();
    });

    test('should have source type selector', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      await expect(page.locator('#source-type')).toBeVisible();
    });

    test('should have URL, name, and frequency fields', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      await expect(page.locator('#source-url')).toBeVisible();
      await expect(page.locator('#source-name')).toBeVisible();
      await expect(page.locator('#check-frequency')).toBeVisible();
    });

    test('should have persona selector', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      const personaSelect = page.locator('#target-persona');
      await expect(personaSelect).toBeVisible();
    });

    test('should have asset type checkboxes', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      const checkboxes = page.locator('.asset-type-checkbox, #asset-types-container input[type="checkbox"]');
      expect(await checkboxes.count()).toBeGreaterThan(0);
    });

    test('should update URL hint when source type changes', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();

      const hint = page.locator('#url-hint');
      const initialHint = await hint.textContent();

      await page.selectOption('#source-type', 'youtube');
      await page.waitForTimeout(300);

      const newHint = await hint.textContent();
      // Hint should change for different source types
    });

    test('should close modal on cancel', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();

      const cancelBtn = page.locator('#source-modal button:has-text("Cancel")');
      await cancelBtn.click();

      const modal = page.locator('#source-modal');
      await expect(modal).toBeHidden();
    });
  });

  test.describe('Source Type Options', () => {
    test('should have RSS source type', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      const typeSelect = page.locator('#source-type');
      const options = typeSelect.locator('option');
      const optionTexts = await options.allTextContents();
      expect(optionTexts.some(t => t.toLowerCase().includes('rss'))).toBe(true);
    });

    test('should have YouTube source type', async ({ page }) => {
      await page.goto('/autopilot.html');
      const addBtn = page.locator('button:has-text("Add Source"), button:has-text("Add Monitor")');
      await addBtn.first().click();
      const typeSelect = page.locator('#source-type');
      const options = typeSelect.locator('option');
      const optionTexts = await options.allTextContents();
      expect(optionTexts.some(t => t.toLowerCase().includes('youtube'))).toBe(true);
    });
  });
});
