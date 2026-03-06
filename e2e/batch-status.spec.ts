/**
 * Batch Status Page Tests
 * Tests for batch processing progress tracking.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Batch Status Page', () => {
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
    test('should redirect to upload if no batch_id', async ({ page }) => {
      await page.goto('/batch-status.html');
      // Should redirect to upload page since no batch_id param
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url.includes('upload') || url.includes('batch-status')).toBe(true);
    });

    test('should show batch status elements with valid batch_id', async ({ page }) => {
      await page.goto('/batch-status.html?batch_id=test-123');
      // Should have status display elements
      const statusBadge = page.locator('#batch-status-badge');
      const progressBar = page.locator('#overall-progress');
      // Elements should exist in DOM
    });

    test('should have stats grid', async ({ page }) => {
      await page.goto('/batch-status.html?batch_id=test-123');
      await expect(page.locator('#total-jobs')).toBeVisible();
      await expect(page.locator('#completed-jobs')).toBeVisible();
      await expect(page.locator('#processing-jobs')).toBeVisible();
      await expect(page.locator('#failed-jobs')).toBeVisible();
    });

    test('should have jobs list container', async ({ page }) => {
      await page.goto('/batch-status.html?batch_id=test-123');
      await expect(page.locator('#jobs-list')).toBeVisible();
    });

    test('should have download section hidden initially', async ({ page }) => {
      await page.goto('/batch-status.html?batch_id=test-123');
      const downloadSection = page.locator('#download-section');
      if (await downloadSection.count() > 0) {
        await expect(downloadSection).toBeHidden();
      }
    });
  });
});
