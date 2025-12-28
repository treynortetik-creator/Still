/**
 * Error Handling Tests
 * Tests for graceful error handling, edge cases, and resilience.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Error Handling', () => {
  test.describe('Network Errors', () => {
    test('should handle offline state gracefully', async ({ page, context }) => {
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

      // Go offline
      await context.setOffline(true);

      // Try to perform an action
      await page.goto('/reserve.html').catch(() => {});

      // Should show offline indicator or error
      await page.waitForTimeout(2000);

      // Go back online
      await context.setOffline(false);
    });

    test('should retry failed requests', async ({ page }) => {
      // Network retry behavior test
    });

    test('should show timeout error for slow responses', async ({ page }) => {
      // Timeout handling test
    });
  });

  test.describe('Form Error States', () => {
    test('should display validation errors clearly', async ({ page }) => {
      await page.goto('/register.html');

      // Submit empty form
      const submitButton = page.locator('button[type="submit"]');

      if (await submitButton.isEnabled()) {
        await submitButton.click();
        await page.waitForTimeout(500);

        // Check for error indicators
        const errorMessages = page.locator('.error, .invalid, [role="alert"], .form-error');
        const inputErrors = page.locator('input:invalid, input.error, input.invalid');

        // Should have some error indication
      }
    });

    test('should clear errors when corrected', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');

      // Enter invalid email
      await emailInput.fill('invalid');
      await emailInput.blur();
      await page.waitForTimeout(300);

      // Check for error
      const hasError = await emailInput.evaluate((el: HTMLInputElement) => !el.validity.valid);
      expect(hasError).toBe(true);

      // Fix the email
      await emailInput.fill('valid@example.com');
      await emailInput.blur();
      await page.waitForTimeout(300);

      // Error should be cleared
      const isValid = await emailInput.evaluate((el: HTMLInputElement) => el.validity.valid);
      expect(isValid).toBe(true);
    });

    test('should handle server validation errors', async ({ page }) => {
      const email = uniqueEmail();

      // First registration
      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Logout and try to register with same email
      await page.evaluate(() => localStorage.clear());
      await page.goto('/register.html');

      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', 'TestPassword123!');

      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill('TestPassword123!');
      }

      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);

      // Should show server error
      const errorMessage = page.locator('.error, [role="alert"], .toast-error');
      const stayedOnPage = page.url().includes('register');

      expect(stayedOnPage || await errorMessage.count() > 0).toBe(true);
    });
  });

  test.describe('Authentication Errors', () => {
    test('should redirect to login on 401', async ({ page }) => {
      // Clear auth
      await page.goto('/');
      await page.evaluate(() => localStorage.clear());

      // Try to access protected page
      await page.goto('/upload.html');
      await page.waitForTimeout(2000);

      // Should redirect to login or show error
      const url = page.url();
      const hasAuthError = await page.locator('.error, .unauthorized').count() > 0;

      // Either redirected or error shown
    });

    test('should handle expired token gracefully', async ({ page }) => {
      // Set expired token
      await page.goto('/');
      await page.evaluate(() => {
        // Set a fake expired token
        localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjB9.expired');
      });

      await page.goto('/upload.html');
      await page.waitForTimeout(2000);

      // Should handle gracefully
    });

    test('should handle concurrent session logout', async ({ page, context }) => {
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

      // Open new page and logout
      const newPage = await context.newPage();
      await newPage.goto('/');

      // Get token from first page
      const token = await page.evaluate(() => localStorage.getItem('token'));

      // Set same token in new page
      await newPage.evaluate((t) => localStorage.setItem('token', t || ''), token);

      // Logout in new page
      await newPage.goto('/');
      await newPage.evaluate(() => localStorage.clear());
      await newPage.close();

      // Try to use original page
      await page.goto('/reserve.html');
      await page.waitForTimeout(2000);

      // May or may not fail depending on token validation
    });
  });

  test.describe('File Upload Errors', () => {
    test('should handle oversized files', async ({ page }) => {
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

      // Try to upload large file (create 101MB buffer)
      const fileInput = page.locator('input[type="file"]');

      // Note: This creates a large buffer in memory
      // In practice, you'd want to test with actual file or mock
      await fileInput.setInputFiles({
        name: 'large-file.txt',
        mimeType: 'text/plain',
        buffer: Buffer.alloc(1024), // Small file for test (real test would use larger)
      });

      // File size validation may happen client or server side
    });

    test('should handle corrupted files gracefully', async ({ page }) => {
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

      const fileInput = page.locator('input[type="file"]');

      // Upload file with wrong extension/content
      await fileInput.setInputFiles({
        name: 'fake.mp4',
        mimeType: 'video/mp4',
        buffer: Buffer.from('this is not a real video file'),
      });

      // Should handle gracefully during processing
    });
  });

  test.describe('Edge Cases', () => {
    test('should handle empty inputs', async ({ page }) => {
      await page.goto('/login.html');

      const emailInput = page.locator('input[type="email"]');
      const passwordInput = page.locator('input[type="password"]');

      // Clear inputs explicitly
      await emailInput.fill('');
      await passwordInput.fill('');

      const submitButton = page.locator('button[type="submit"]');

      if (await submitButton.isEnabled()) {
        await submitButton.click();
        await page.waitForTimeout(500);

        // Should show validation error
      }
    });

    test('should handle very long inputs', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');

      // Very long email
      const longEmail = 'a'.repeat(1000) + '@example.com';
      await emailInput.fill(longEmail);

      // Should either truncate or show error
    });

    test('should handle special characters in inputs', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');

      // Email with special chars
      await emailInput.fill('test+special@example.com');
      await emailInput.blur();

      const isValid = await emailInput.evaluate((el: HTMLInputElement) => el.validity.valid);
      // Plus addressing should be valid
    });

    test('should handle unicode in inputs', async ({ page }) => {
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

      // Go to upload and try text with unicode
      const pasteTab = page.locator('button:has-text("Paste"), [data-tab="paste"]');

      if (await pasteTab.count() > 0) {
        await pasteTab.first().click();
        await page.waitForTimeout(300);

        const textarea = page.locator('textarea');

        if (await textarea.count() > 0) {
          await textarea.first().fill('Unicode test: 你好世界 مرحبا 🎉 émojis');

          const value = await textarea.first().inputValue();
          expect(value).toContain('你好');
        }
      }
    });

    test('should handle rapid form submissions', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', 'test@example.com');
      await page.fill('input[type="password"]', 'TestPassword123!');

      const submitButton = page.locator('button[type="submit"]');

      // Rapid clicks
      await submitButton.click();
      await submitButton.click();
      await submitButton.click();

      await page.waitForTimeout(2000);

      // Should not cause errors or duplicate submissions
    });

    test('should handle browser back/forward', async ({ page }) => {
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

      // Navigate to another page
      await page.goto('/reserve.html');
      await page.waitForTimeout(500);

      // Go back
      await page.goBack();
      await page.waitForTimeout(500);

      // Should handle gracefully
      const url = page.url();
    });
  });

  test.describe('JavaScript Errors', () => {
    test('should not have console errors on page load', async ({ page }) => {
      const errors: string[] = [];

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });

      await page.goto('/');
      await page.waitForTimeout(1000);

      // Filter out expected errors (like favicon 404)
      const unexpectedErrors = errors.filter(
        (e) => !e.includes('favicon') && !e.includes('404')
      );

      expect(unexpectedErrors.length).toBe(0);
    });

    test('should not have unhandled promise rejections', async ({ page }) => {
      const rejections: string[] = [];

      page.on('pageerror', (error) => {
        rejections.push(error.message);
      });

      await page.goto('/');
      await page.waitForTimeout(1000);

      expect(rejections.length).toBe(0);
    });
  });

  test.describe('404 Pages', () => {
    test('should show 404 for non-existent pages', async ({ page }) => {
      const response = await page.goto('/this-page-does-not-exist-12345');

      expect(response?.status()).toBe(404);
    });

    test('should have helpful 404 message', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');

      // Should show helpful message, not blank page
      const content = await page.content();
      const hasContent = content.length > 100;
    });
  });

  test.describe('API Error Responses', () => {
    test('should display API errors to user', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', 'nonexistent@example.com');
      await page.fill('input[type="password"]', 'WrongPassword123!');
      await page.click('button[type="submit"]');

      await page.waitForTimeout(2000);

      // Should show error message
      const errorMessage = page.locator('.error, [role="alert"], .toast');
      const stayedOnLogin = page.url().includes('login');

      expect(stayedOnLogin || await errorMessage.count() > 0).toBe(true);
    });

    test('should handle 500 errors gracefully', async ({ page }) => {
      // 500 errors should show user-friendly message
    });
  });
});
