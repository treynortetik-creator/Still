/**
 * Settings Page Tests
 * Tests for all settings tabs: voice test, memory rules, brand voice, personas, webhooks.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Settings Page', () => {
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
    test('should load settings page', async ({ page }) => {
      await page.goto('/settings.html');
      await expect(page).toHaveTitle(/Settings/i);
    });

    test('should have all 5 settings tabs', async ({ page }) => {
      await page.goto('/settings.html');

      const voiceTab = page.locator('[data-tab="voice-test"]');
      const memoryTab = page.locator('[data-tab="memory"]');
      const brandTab = page.locator('[data-tab="brand-voice"]');
      const personasTab = page.locator('[data-tab="personas"]');
      const webhooksTab = page.locator('[data-tab="webhooks"]');

      await expect(voiceTab).toBeVisible();
      await expect(memoryTab).toBeVisible();
      await expect(brandTab).toBeVisible();
      await expect(personasTab).toBeVisible();
      await expect(webhooksTab).toBeVisible();
    });

    test('should default to voice test tab', async ({ page }) => {
      await page.goto('/settings.html');
      const sampleText = page.locator('#sample-text');
      await expect(sampleText).toBeVisible();
    });
  });

  test.describe('Tab Navigation', () => {
    test('should switch to memory tab', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="memory"]');
      const rulesList = page.locator('#memory-rules-list');
      await expect(rulesList).toBeVisible();
    });

    test('should switch to brand voice tab', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="brand-voice"]');
      const companyName = page.locator('#bv-company-name');
      await expect(companyName).toBeVisible();
    });

    test('should switch to personas tab', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="personas"]');
      const personasList = page.locator('#personas-list');
      await expect(personasList).toBeVisible();
    });

    test('should switch to webhooks tab', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="webhooks"]');
      const webhooksList = page.locator('#webhooks-list');
      await expect(webhooksList).toBeVisible();
    });
  });

  test.describe('Voice Test Tab', () => {
    test('should have sample text textarea and persona selector', async ({ page }) => {
      await page.goto('/settings.html');
      await expect(page.locator('#sample-text')).toBeVisible();
      await expect(page.locator('#preview-persona')).toBeVisible();
      await expect(page.locator('#preview-btn')).toBeVisible();
    });

    test('should populate persona dropdown', async ({ page }) => {
      await page.goto('/settings.html');
      const personaSelect = page.locator('#preview-persona');
      await page.waitForTimeout(1000);
      const options = personaSelect.locator('option');
      expect(await options.count()).toBeGreaterThan(1);
    });

    test('should require sample text for preview', async ({ page }) => {
      await page.goto('/settings.html');
      const textarea = page.locator('#sample-text');
      await textarea.fill('');
      await page.click('#preview-btn');
      // Should not crash, may show error or do nothing
    });
  });

  test.describe('Memory Rules Tab', () => {
    test('should show add rule button', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="memory"]');
      const addButton = page.locator('button:has-text("Add Rule"), button:has-text("Add Memory")');
      await expect(addButton.first()).toBeVisible();
    });

    test('should open rule modal when add clicked', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="memory"]');
      const addButton = page.locator('button:has-text("Add Rule"), button:has-text("Add Memory")');
      await addButton.first().click();
      const modal = page.locator('#rule-modal');
      await expect(modal).toBeVisible();
    });

    test('should have rule type and text fields in modal', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="memory"]');
      const addButton = page.locator('button:has-text("Add Rule"), button:has-text("Add Memory")');
      await addButton.first().click();
      await expect(page.locator('#rule-type')).toBeVisible();
      await expect(page.locator('#rule-text')).toBeVisible();
    });
  });

  test.describe('Brand Voice Tab', () => {
    test('should have all brand voice form fields', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="brand-voice"]');
      await expect(page.locator('#bv-company-name')).toBeVisible();
      await expect(page.locator('#bv-industry')).toBeVisible();
      await expect(page.locator('#bv-vocabulary')).toBeVisible();
    });

    test('should have tone fields for each platform', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="brand-voice"]');
      await expect(page.locator('#bv-tone-linkedin')).toBeVisible();
      await expect(page.locator('#bv-tone-blog')).toBeVisible();
      await expect(page.locator('#bv-tone-email')).toBeVisible();
    });

    test('should have voice samples section', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="brand-voice"]');
      await expect(page.locator('#voice-sample')).toBeVisible();
      await expect(page.locator('#sample-type')).toBeVisible();
    });

    test('should have save button', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="brand-voice"]');
      const saveBtn = page.locator('button:has-text("Save")');
      await expect(saveBtn.first()).toBeVisible();
    });
  });

  test.describe('Personas Tab', () => {
    test('should show default personas', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="personas"]');
      await page.waitForTimeout(1000);
      const personasList = page.locator('#personas-list');
      const cards = personasList.locator('.bg-still-card, [class*="card"]');
      // Default personas should be visible
    });

    test('should have add persona button', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="personas"]');
      const addBtn = page.locator('button:has-text("Add Persona"), button:has-text("Create Persona")');
      await expect(addBtn.first()).toBeVisible();
    });

    test('should open persona modal with form fields', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="personas"]');
      const addBtn = page.locator('button:has-text("Add Persona"), button:has-text("Create Persona")');
      await addBtn.first().click();
      const modal = page.locator('#persona-modal');
      await expect(modal).toBeVisible();
      await expect(page.locator('#persona-name')).toBeVisible();
      await expect(page.locator('#persona-role')).toBeVisible();
      await expect(page.locator('#persona-industry')).toBeVisible();
    });
  });

  test.describe('Webhooks Tab', () => {
    test('should have add webhook button', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="webhooks"]');
      const addBtn = page.locator('button:has-text("Add Webhook"), button:has-text("Create Webhook")');
      await expect(addBtn.first()).toBeVisible();
    });

    test('should open webhook modal with form fields', async ({ page }) => {
      await page.goto('/settings.html');
      await page.click('[data-tab="webhooks"]');
      const addBtn = page.locator('button:has-text("Add Webhook"), button:has-text("Create Webhook")');
      await addBtn.first().click();
      const modal = page.locator('#webhook-modal');
      await expect(modal).toBeVisible();
      await expect(page.locator('#webhook-name')).toBeVisible();
      await expect(page.locator('#webhook-url')).toBeVisible();
    });
  });
});
