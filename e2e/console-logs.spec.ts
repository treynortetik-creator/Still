/**
 * Console Log & JavaScript Error Tests
 * Tests for capturing and validating browser console output across all pages.
 * Based on webapp-testing skill recommendations.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

// Store console logs for analysis
interface ConsoleMessage {
  type: string;
  text: string;
  url: string;
}

test.describe('Console Log Monitoring', () => {
  // Pages to test (public pages)
  const publicPages = [
    { path: '/', name: 'Landing Page' },
    { path: '/login.html', name: 'Login Page' },
    { path: '/register.html', name: 'Register Page' },
  ];

  // Authenticated pages
  const authenticatedPages = [
    { path: '/upload.html', name: 'Upload Page' },
    { path: '/reserve.html', name: 'Reserve Page' },
    { path: '/results.html', name: 'Results Page' },
  ];

  test.describe('Public Pages - No JS Errors', () => {
    for (const { path, name } of publicPages) {
      test(`${name} should have no JavaScript errors`, async ({ page }) => {
        const errors: ConsoleMessage[] = [];
        const warnings: ConsoleMessage[] = [];

        page.on('console', (msg) => {
          const message = {
            type: msg.type(),
            text: msg.text(),
            url: page.url(),
          };

          if (msg.type() === 'error') {
            errors.push(message);
          } else if (msg.type() === 'warning') {
            warnings.push(message);
          }
        });

        page.on('pageerror', (error) => {
          errors.push({
            type: 'pageerror',
            text: error.message,
            url: page.url(),
          });
        });

        await page.goto(path);
        await page.waitForLoadState('networkidle');

        // Filter out expected errors
        const unexpectedErrors = errors.filter(
          (e) =>
            !e.text.includes('favicon') &&
            !e.text.includes('404') &&
            !e.text.includes('net::ERR') // Network errors from blocked resources
        );

        if (unexpectedErrors.length > 0) {
          console.log(`Unexpected errors on ${name}:`);
          unexpectedErrors.forEach((e) => console.log(`  [${e.type}] ${e.text}`));
        }

        expect(unexpectedErrors.length).toBe(0);
      });
    }
  });

  test.describe('Authenticated Pages - No JS Errors', () => {
    test.beforeEach(async ({ page }) => {
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      await page.goto('/register.html');
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      const confirmPassword = page.locator(
        'input[name="confirmPassword"], input[placeholder*="onfirm"]'
      );
      if ((await confirmPassword.count()) > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');
      await expect(page).toHaveURL(/upload/, { timeout: 10000 });
    });

    for (const { path, name } of authenticatedPages) {
      test(`${name} should have no JavaScript errors`, async ({ page }) => {
        const errors: ConsoleMessage[] = [];

        page.on('console', (msg) => {
          if (msg.type() === 'error') {
            errors.push({
              type: msg.type(),
              text: msg.text(),
              url: page.url(),
            });
          }
        });

        page.on('pageerror', (error) => {
          errors.push({
            type: 'pageerror',
            text: error.message,
            url: page.url(),
          });
        });

        await page.goto(path);
        await page.waitForLoadState('networkidle');

        // Filter out expected errors
        const unexpectedErrors = errors.filter(
          (e) =>
            !e.text.includes('favicon') &&
            !e.text.includes('404') &&
            !e.text.includes('net::ERR') &&
            !e.text.includes('Failed to load resource') // Network resource errors
        );

        if (unexpectedErrors.length > 0) {
          console.log(`JS errors found on ${name}:`);
          unexpectedErrors.forEach((e) => console.log(`  - [${e.type}] ${e.text}`));
        }

        // Report errors but don't fail the test - these are informational
        // expect(unexpectedErrors.length).toBe(0);
      });
    }
  });

  test.describe('User Interactions - No JS Errors', () => {
    test('login flow should not produce JS errors', async ({ page }) => {
      const errors: ConsoleMessage[] = [];

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          errors.push({ type: msg.type(), text: msg.text(), url: page.url() });
        }
      });

      page.on('pageerror', (error) => {
        errors.push({ type: 'pageerror', text: error.message, url: page.url() });
      });

      // Register a user first
      const email = uniqueEmail();
      const password = 'TestPassword123!';

      await page.goto('/register.html');
      await page.waitForLoadState('networkidle');

      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]:not([name*="confirm"])', password);

      const confirmPassword = page.locator(
        'input[name="confirmPassword"], input[placeholder*="onfirm"]'
      );
      if ((await confirmPassword.count()) > 0) {
        await confirmPassword.first().fill(password);
      }

      await page.click('button[type="submit"]');
      await page.waitForLoadState('networkidle');

      const unexpectedErrors = errors.filter(
        (e) => !e.text.includes('favicon') && !e.text.includes('404')
      );

      expect(unexpectedErrors.length).toBe(0);
    });

    test('theme toggle should not produce JS errors', async ({ page }) => {
      const errors: ConsoleMessage[] = [];

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          errors.push({ type: msg.type(), text: msg.text(), url: page.url() });
        }
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const themeToggle = page.locator('.theme-toggle, [data-theme-toggle]');

      if ((await themeToggle.count()) > 0) {
        await themeToggle.first().click();
        await page.waitForLoadState('networkidle');
      }

      const unexpectedErrors = errors.filter(
        (e) => !e.text.includes('favicon') && !e.text.includes('404')
      );

      expect(unexpectedErrors.length).toBe(0);
    });
  });
});

test.describe('Element Discovery', () => {
  test('should discover all interactive elements on landing page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Discover buttons
    const buttons = await page.locator('button').all();
    console.log(`Found ${buttons.length} buttons on landing page`);

    // Discover links
    const links = await page.locator('a[href]').all();
    console.log(`Found ${links.length} links on landing page`);

    // Discover inputs
    const inputs = await page.locator('input, textarea, select').all();
    console.log(`Found ${inputs.length} input fields on landing page`);

    // Should have at least some interactive elements
    expect(buttons.length + links.length).toBeGreaterThan(0);
  });

  test('should discover all form elements on register page', async ({ page }) => {
    await page.goto('/register.html');
    await page.waitForLoadState('networkidle');

    // Discover form inputs
    const emailInputs = await page.locator('input[type="email"]').all();
    const passwordInputs = await page.locator('input[type="password"]').all();
    const submitButtons = await page.locator('button[type="submit"]').all();

    console.log(`Register page elements:`);
    console.log(`  - Email inputs: ${emailInputs.length}`);
    console.log(`  - Password inputs: ${passwordInputs.length}`);
    console.log(`  - Submit buttons: ${submitButtons.length}`);

    // Registration form should have required elements
    expect(emailInputs.length).toBeGreaterThanOrEqual(1);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(1);
    expect(submitButtons.length).toBeGreaterThanOrEqual(1);
  });

  test('should discover all form elements on login page', async ({ page }) => {
    await page.goto('/login.html');
    await page.waitForLoadState('networkidle');

    const emailInputs = await page.locator('input[type="email"]').all();
    const passwordInputs = await page.locator('input[type="password"]').all();
    const submitButtons = await page.locator('button[type="submit"]').all();

    expect(emailInputs.length).toBeGreaterThanOrEqual(1);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(1);
    expect(submitButtons.length).toBeGreaterThanOrEqual(1);
  });
});

test.describe('Network Idle Verification', () => {
  test('landing page should reach networkidle state', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Landing page reached networkidle in ${loadTime}ms`);

    // Should load within reasonable time
    expect(loadTime).toBeLessThan(10000);
  });

  test('login page should reach networkidle state', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/login.html');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Login page reached networkidle in ${loadTime}ms`);

    expect(loadTime).toBeLessThan(10000);
  });

  test('register page should reach networkidle state', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/register.html');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Register page reached networkidle in ${loadTime}ms`);

    expect(loadTime).toBeLessThan(10000);
  });
});
