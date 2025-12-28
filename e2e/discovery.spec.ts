/**
 * Element Discovery & Reconnaissance Tests
 * Uses the reconnaissance-then-action pattern from webapp-testing skill.
 * These tests help discover page structure and validate selectors.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Page Structure Discovery', () => {
  test.describe('Public Pages', () => {
    test('discover landing page structure', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Take screenshot for visual reference
      await page.screenshot({ path: 'test-results/landing-page.png', fullPage: true });

      // Discover page structure
      const structure = {
        title: await page.title(),
        headings: await page.locator('h1, h2, h3').allTextContents(),
        buttons: await page.locator('button').count(),
        links: await page.locator('a[href]').count(),
        images: await page.locator('img').count(),
        forms: await page.locator('form').count(),
        navigation: await page.locator('nav, .nav, .navigation').count(),
      };

      console.log('Landing Page Structure:', JSON.stringify(structure, null, 2));

      // Basic structure expectations
      expect(structure.title.length).toBeGreaterThan(0);
    });

    test('discover login page structure', async ({ page }) => {
      await page.goto('/login.html');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'test-results/login-page.png', fullPage: true });

      const formElements = {
        emailField: await page.locator('input[type="email"]').count(),
        passwordField: await page.locator('input[type="password"]').count(),
        submitButton: await page.locator('button[type="submit"]').count(),
        registerLink: await page.locator('a[href*="register"]').count(),
        formLabels: await page.locator('label').count(),
      };

      console.log('Login Form Elements:', JSON.stringify(formElements, null, 2));

      expect(formElements.emailField).toBeGreaterThanOrEqual(1);
      expect(formElements.passwordField).toBeGreaterThanOrEqual(1);
      expect(formElements.submitButton).toBeGreaterThanOrEqual(1);
    });

    test('discover register page structure', async ({ page }) => {
      await page.goto('/register.html');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'test-results/register-page.png', fullPage: true });

      const formElements = {
        emailField: await page.locator('input[type="email"]').count(),
        passwordFields: await page.locator('input[type="password"]').count(),
        submitButton: await page.locator('button[type="submit"]').count(),
        loginLink: await page.locator('a[href*="login"]').count(),
      };

      console.log('Register Form Elements:', JSON.stringify(formElements, null, 2));

      expect(formElements.emailField).toBeGreaterThanOrEqual(1);
      expect(formElements.passwordFields).toBeGreaterThanOrEqual(1);
    });
  });

  test.describe('Authenticated Pages', () => {
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

    test('discover upload page structure', async ({ page }) => {
      await page.goto('/upload.html');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'test-results/upload-page.png', fullPage: true });

      const structure = {
        fileInput: await page.locator('input[type="file"]').count(),
        dropZone: await page.locator('.drop-zone, .dropzone, [data-dropzone]').count(),
        textArea: await page.locator('textarea').count(),
        personaSelect: await page.locator('select, .persona-select').count(),
        contentTypeCheckboxes: await page.locator('input[type="checkbox"]').count(),
        submitButton: await page.locator('button[type="submit"], button:has-text("Upload"), button:has-text("Process")').count(),
        tabs: await page.locator('[role="tab"], .tab').count(),
      };

      console.log('Upload Page Structure:', JSON.stringify(structure, null, 2));

      // Should have some way to upload content
      expect(structure.fileInput + structure.textArea).toBeGreaterThan(0);
    });

    test('discover reserve/library page structure', async ({ page }) => {
      await page.goto('/reserve.html');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'test-results/reserve-page.png', fullPage: true });

      const structure = {
        cards: await page.locator('.card, .item, article').count(),
        filters: await page.locator('select, .filter, [data-filter]').count(),
        searchInput: await page.locator('input[type="search"], input[placeholder*="earch"]').count(),
        checkboxes: await page.locator('input[type="checkbox"]').count(),
        generateButton: await page.locator('button:has-text("Generate")').count(),
      };

      console.log('Reserve Page Structure:', JSON.stringify(structure, null, 2));
    });

    test('discover results page structure', async ({ page }) => {
      await page.goto('/results.html');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'test-results/results-page.png', fullPage: true });

      const structure = {
        outputCards: await page.locator('.output-card, .content-card, .result-item').count(),
        copyButtons: await page.locator('button:has-text("Copy")').count(),
        exportButtons: await page.locator('button:has-text("Export")').count(),
        tabs: await page.locator('[role="tab"], .tab').count(),
        feedbackButtons: await page.locator('[data-feedback], .thumbs-up, .thumbs-down').count(),
      };

      console.log('Results Page Structure:', JSON.stringify(structure, null, 2));
    });
  });
});

test.describe('Selector Validation', () => {
  test('validate login form selectors work', async ({ page }) => {
    await page.goto('/login.html');
    await page.waitForLoadState('networkidle');

    // Test that our standard selectors find elements
    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');
    const submitButton = page.locator('button[type="submit"]');

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitButton).toBeVisible();

    // Test that we can interact with them
    await emailInput.fill('test@example.com');
    await passwordInput.fill('password123');

    expect(await emailInput.inputValue()).toBe('test@example.com');
    expect(await passwordInput.inputValue()).toBe('password123');
  });

  test('validate register form selectors work', async ({ page }) => {
    await page.goto('/register.html');
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]:not([name*="confirm"])');
    const confirmPasswordInput = page.locator(
      'input[name="confirmPassword"], input[placeholder*="onfirm"], input[type="password"]:nth-of-type(2)'
    );

    await expect(emailInput).toBeVisible();
    await expect(passwordInput.first()).toBeVisible();

    // Fill and verify
    await emailInput.fill('test@example.com');
    await passwordInput.first().fill('TestPassword123!');

    expect(await emailInput.inputValue()).toBe('test@example.com');
  });
});

test.describe('Dynamic Content Loading', () => {
  test('verify dynamic content loads after networkidle', async ({ page }) => {
    const email = uniqueEmail();
    const password = 'TestPassword123!';

    // Register
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

    // Navigate to reserve page
    await page.goto('/reserve.html');

    // Wait for networkidle - content should be loaded
    await page.waitForLoadState('networkidle');

    // Take screenshot of loaded state
    await page.screenshot({ path: 'test-results/reserve-loaded.png', fullPage: true });

    // Page should have some content (even if empty state)
    const pageContent = await page.content();
    expect(pageContent.length).toBeGreaterThan(1000);
  });
});
