/**
 * Shared test fixtures and utilities for ContentMultiplier E2E tests.
 */
import { test as base, expect, Page } from '@playwright/test';

// Test user credentials
export const TEST_USER = {
  email: `test-${Date.now()}@example.com`,
  password: 'TestPassword123!',
};

// Reusable authenticated test fixture
export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ page }, use) => {
    // Register a new user
    await page.goto('/register.html');
    await page.fill('input[type="email"]', TEST_USER.email);
    await page.fill('input[type="password"]', TEST_USER.password);

    // Handle confirm password if present
    const confirmPassword = page.locator('input[name="confirmPassword"], input[placeholder*="Confirm"]');
    if (await confirmPassword.isVisible()) {
      await confirmPassword.fill(TEST_USER.password);
    }

    await page.click('button[type="submit"]');

    // Wait for redirect to upload page
    await page.waitForURL(/upload|dashboard/);

    await use(page);
  },
});

// Helper to login with existing credentials
export async function login(page: Page, email: string, password: string) {
  await page.goto('/login.html');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/upload|dashboard|reserve/);
}

// Helper to logout
export async function logout(page: Page) {
  // Try multiple logout methods
  const logoutButton = page.locator('button:has-text("Logout"), a:has-text("Logout"), [data-logout]');
  if (await logoutButton.isVisible()) {
    await logoutButton.click();
  } else {
    // Clear localStorage and redirect
    await page.evaluate(() => {
      localStorage.removeItem('token');
      localStorage.removeItem('auth_token');
    });
    await page.goto('/login.html');
  }
}

// Helper to check if user is authenticated
export async function isAuthenticated(page: Page): Promise<boolean> {
  const token = await page.evaluate(() => {
    return localStorage.getItem('token') || localStorage.getItem('auth_token');
  });
  return !!token;
}

// Helper to generate unique email
export function uniqueEmail(): string {
  return `test-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
}

// Helper to wait for API response
export async function waitForApiResponse(page: Page, urlPattern: string | RegExp) {
  return page.waitForResponse((response) => {
    const url = response.url();
    if (typeof urlPattern === 'string') {
      return url.includes(urlPattern);
    }
    return urlPattern.test(url);
  });
}

// Helper to create a test file for upload
export async function createTestFile(page: Page, filename: string, content: string, mimeType: string) {
  const buffer = Buffer.from(content);
  return {
    name: filename,
    mimeType,
    buffer,
  };
}

// Helper to check for toast/notification messages
export async function checkToast(page: Page, expectedText: string) {
  const toast = page.locator('.toast, .notification, [role="alert"], .message');
  await expect(toast).toContainText(expectedText, { timeout: 5000 });
}

// Helper to fill upload form
export async function fillUploadForm(page: Page, options: {
  persona?: string;
  contentTypes?: string[];
  campaignName?: string;
}) {
  if (options.persona) {
    const personaSelect = page.locator('select[name="persona"], #persona, [data-persona]');
    await personaSelect.selectOption({ label: options.persona });
  }

  if (options.contentTypes) {
    for (const contentType of options.contentTypes) {
      const checkbox = page.locator(`input[type="checkbox"][value="${contentType}"], label:has-text("${contentType}") input`);
      await checkbox.check();
    }
  }

  if (options.campaignName) {
    const campaignInput = page.locator('input[name="campaignName"], #campaignName, [data-campaign]');
    await campaignInput.fill(options.campaignName);
  }
}

export { expect };
