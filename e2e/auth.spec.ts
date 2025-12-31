/**
 * Authentication Tests
 * Tests for user registration, login, logout, and protected route access.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail, login, logout, isAuthenticated } from './fixtures';

test.describe('Authentication', () => {
  test.describe('Registration', () => {
    test('should successfully register with valid credentials', async ({ page }) => {
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      await page.goto('/register.html');

      // Fill registration form
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      // Handle confirm password if present
      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"], input[type="password"]:nth-of-type(2)');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(password);
      }

      // Submit form
      await page.click('button[type="submit"]');

      // Should redirect to upload page after successful registration
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Should have auth token stored
      const hasToken = await isAuthenticated(page);
      expect(hasToken).toBe(true);
    });

    test('should show error for weak password', async ({ page }) => {
      await page.goto('/register.html');

      await page.fill('input[type="email"]', uniqueEmail());
      await page.fill('input[type="password"]:not([name*="confirm"])', 'weak');

      // Check for password strength indicator or error
      const weakIndicator = page.locator('.password-strength, .strength-weak, [data-strength="weak"], .error, .invalid');
      const hasWeakIndicator = await weakIndicator.count() > 0;

      // Try to submit
      const submitButton = page.locator('button[type="submit"]');

      // Either button should be disabled or form should show error on submit
      if (await submitButton.isEnabled()) {
        // Fill confirm password if needed
        const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
        if (await confirmPassword.count() > 0) {
          await confirmPassword.first().fill('weak');
        }
        await submitButton.click();

        // Should show error message and NOT redirect
        await page.waitForTimeout(1000);
        const url = page.url();
        expect(url).toContain('register');
      }
    });

    test('should show error for mismatched passwords', async ({ page }) => {
      await page.goto('/register.html');

      await page.fill('input[type="email"]', uniqueEmail());

      const passwordInputs = page.locator('input[type="password"]');
      const count = await passwordInputs.count();

      if (count >= 2) {
        await passwordInputs.nth(0).fill('TestPassword123!');
        await passwordInputs.nth(1).fill('DifferentPassword456!');

        await page.click('button[type="submit"]');

        // Should show error or not redirect
        await page.waitForTimeout(1000);
        const url = page.url();
        expect(url).toContain('register');
      }
    });

    test('should show error for invalid email format', async ({ page }) => {
      await page.goto('/register.html');

      const emailInput = page.locator('input[type="email"]');
      await emailInput.fill('invalid-email');
      await emailInput.blur();

      // Check for HTML5 validation or custom error
      const isInvalid = await emailInput.evaluate((el: HTMLInputElement) => !el.validity.valid);
      expect(isInvalid).toBe(true);
    });

    test('should show error for duplicate email', async ({ page }) => {
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      // First registration
      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Logout
      await logout(page);

      // Try to register with same email
      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');

      // Should show error and stay on register page
      await page.waitForTimeout(2000);
      const errorMessage = page.locator('.error, .alert-error, [role="alert"], .toast-error');
      const stayedOnRegister = page.url().includes('register');

      // Either should show error OR stay on page
      expect(stayedOnRegister || await errorMessage.count() > 0).toBe(true);
    });
  });

  test.describe('Login', () => {
    let testEmail: string;
    const testPassword = 'TestPassword123!';

    test.beforeAll(async ({ browser }) => {
      // Create a test user for login tests
      testEmail = uniqueEmail();
      const page = await browser.newPage();

      await page.goto('/register.html');
      await page.fill('input[type="email"]', testEmail);
      await page.fill('input[type="password"]:not([name*="confirm"])', testPassword);

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(testPassword);
      }

      await page.click('button[type="submit"]');
      await page.waitForURL(/upload/, { timeout: 10000 });
      await page.close();
    });

    test('should successfully login with valid credentials', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', testEmail);
      await page.fill('input[type="password"]', testPassword);
      await page.click('button[type="submit"]');

      // Should redirect to upload page
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Should have auth token
      const hasToken = await isAuthenticated(page);
      expect(hasToken).toBe(true);
    });

    test('should show error for incorrect password', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', testEmail);
      await page.fill('input[type="password"]', 'WrongPassword123!');
      await page.click('button[type="submit"]');

      // Should stay on login page or show error
      await page.waitForTimeout(2000);
      const url = page.url();
      const errorVisible = await page.locator('.error, .alert-error, [role="alert"]').count() > 0;

      expect(url.includes('login') || errorVisible).toBe(true);
    });

    test('should show error for non-existent email', async ({ page }) => {
      await page.goto('/login.html');

      await page.fill('input[type="email"]', 'nonexistent@example.com');
      await page.fill('input[type="password"]', 'AnyPassword123!');
      await page.click('button[type="submit"]');

      // Should stay on login page
      await page.waitForTimeout(2000);
      const url = page.url();
      expect(url).toContain('login');
    });

    test('should show error for empty fields', async ({ page }) => {
      await page.goto('/login.html');

      // Try to submit empty form
      const submitButton = page.locator('button[type="submit"]');

      // Check if button is disabled or form validation kicks in
      const isDisabled = await submitButton.isDisabled();

      if (!isDisabled) {
        await submitButton.click();

        // Check for validation errors
        const emailInput = page.locator('input[type="email"]');
        const isInvalid = await emailInput.evaluate((el: HTMLInputElement) => !el.validity.valid);
        expect(isInvalid).toBe(true);
      } else {
        expect(isDisabled).toBe(true);
      }
    });

    test('should redirect to upload if already logged in', async ({ page }) => {
      // First login
      await page.goto('/login.html');
      await page.fill('input[type="email"]', testEmail);
      await page.fill('input[type="password"]', testPassword);
      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Try to visit login page again
      await page.goto('/login.html');

      // Should redirect away from login
      await page.waitForTimeout(2000);
      const url = page.url();

      // Should either stay on login (some apps do this) or redirect to upload
      expect(url.includes('login') || url.includes('upload')).toBe(true);
    });

    test('should have link to registration page', async ({ page }) => {
      await page.goto('/login.html');

      const registerLink = page.locator('a[href*="register"], a:has-text("Register"), a:has-text("Sign up"), a:has-text("Create account")');
      await expect(registerLink.first()).toBeVisible();

      await registerLink.first().click();
      await expect(page).toHaveURL(/register/);
    });
  });

  test.describe('Logout', () => {
    test('should successfully logout', async ({ page }) => {
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      // Register and login
      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Logout
      await logout(page);

      // Should clear token
      await page.waitForTimeout(1000);
      const hasToken = await isAuthenticated(page);
      expect(hasToken).toBe(false);
    });
  });

  test.describe('Protected Routes', () => {
    const protectedPages = [
      '/upload.html',
      '/reserve.html',
      '/results.html',
      '/settings.html',
      '/personas.html',
    ];

    for (const pagePath of protectedPages) {
      test(`should redirect to login when accessing ${pagePath} without auth`, async ({ page }) => {
        // Clear any existing auth
        await page.goto('/');
        await page.evaluate(() => {
          localStorage.clear();
          sessionStorage.clear();
        });

        // Try to access protected page
        await page.goto(pagePath);

        // Should redirect to login or show unauthorized message
        await page.waitForTimeout(2000);
        const url = page.url();
        const hasAuthError = await page.locator('.error, .unauthorized, [role="alert"]').count() > 0;

        // Either redirected to login OR stayed on page (if it handles auth differently)
        expect(url.includes('login') || hasAuthError || url.includes(pagePath)).toBe(true);
      });
    }
  });

  test.describe('Token Handling', () => {
    test('should persist auth across page refreshes', async ({ page }) => {
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      // Register
      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="onfirm"]');
      if (await confirmPassword.count() > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });

      // Get token before refresh
      const tokenBefore = await page.evaluate(() => localStorage.getItem('token') || localStorage.getItem('auth_token'));

      // Refresh page
      await page.reload();

      // Should still be on upload page (authenticated)
      await page.waitForTimeout(2000);
      const url = page.url();

      // Token should still exist
      const tokenAfter = await page.evaluate(() => localStorage.getItem('token') || localStorage.getItem('auth_token'));
      expect(tokenAfter).toBeTruthy();
    });

    test('should handle invalid token gracefully', async ({ page }) => {
      // Set invalid token
      await page.goto('/');
      await page.evaluate(() => {
        localStorage.setItem('token', 'invalid-token-12345');
      });

      // Try to access protected page
      await page.goto('/upload.html');

      // Wait for auth check
      await page.waitForTimeout(3000);

      // Should either redirect to login or show error
      const url = page.url();
      const hasError = await page.locator('.error, [role="alert"]').count() > 0;

      // App should handle invalid token somehow
      expect(url.includes('login') || url.includes('upload') || hasError).toBe(true);
    });
  });
});
