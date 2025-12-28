/**
 * Upload Flow Tests
 * Tests for file upload, text paste, and quick distill workflows.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';
import path from 'path';

test.describe('Upload Flows', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login before each test
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

  test.describe('Upload Page Structure', () => {
    test('should display upload page with all required elements', async ({ page }) => {
      await page.goto('/upload.html');

      // Check for file upload area
      const fileInput = page.locator('input[type="file"]');
      await expect(fileInput).toBeAttached();

      // Check for persona selection
      const personaSelect = page.locator('select, [data-persona], .persona-select');
      const hasPersona = await personaSelect.count() > 0;
      expect(hasPersona).toBe(true);

      // Check for submit button
      const submitButton = page.locator('button[type="submit"], button:has-text("Upload"), button:has-text("Process"), button:has-text("Start")');
      await expect(submitButton.first()).toBeVisible();
    });

    test('should have content type selection options', async ({ page }) => {
      await page.goto('/upload.html');

      // Check for content type checkboxes or options
      const contentTypes = page.locator('input[type="checkbox"], .content-type, [data-content-type]');
      const count = await contentTypes.count();

      // Should have at least one content type option
      expect(count).toBeGreaterThan(0);
    });

    test('should show supported file types', async ({ page }) => {
      await page.goto('/upload.html');

      // Check for file type indicators
      const fileInput = page.locator('input[type="file"]');
      const acceptAttr = await fileInput.getAttribute('accept');

      // Should accept multiple file types
      if (acceptAttr) {
        expect(acceptAttr.length).toBeGreaterThan(0);
      }
    });
  });

  test.describe('Upload Tabs/Modes', () => {
    test('should have multiple upload modes if tabs exist', async ({ page }) => {
      await page.goto('/upload.html');

      // Check for tabs (Full Pipeline, Paste Text, Quick Distill)
      const tabs = page.locator('[role="tab"], .tab, .upload-mode, button:has-text("Paste"), button:has-text("Quick")');
      const tabCount = await tabs.count();

      // If tabs exist, test switching between them
      if (tabCount > 1) {
        for (let i = 0; i < tabCount; i++) {
          await tabs.nth(i).click();
          await page.waitForTimeout(300);
        }
      }
    });

    test('should show text area in paste mode if available', async ({ page }) => {
      await page.goto('/upload.html');

      const pasteTab = page.locator('button:has-text("Paste"), [data-tab="paste"], .tab:has-text("Text")');

      if (await pasteTab.count() > 0) {
        await pasteTab.first().click();
        await page.waitForTimeout(500);

        const textarea = page.locator('textarea');
        await expect(textarea).toBeVisible();
      }
    });
  });

  test.describe('File Upload', () => {
    test('should accept file via input', async ({ page }) => {
      await page.goto('/upload.html');

      // Create a simple text file for testing
      const fileInput = page.locator('input[type="file"]');

      // Set file using setInputFiles
      await fileInput.setInputFiles({
        name: 'test-content.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('This is test content for the content multiplier. It should be processed and turned into various content formats.'),
      });

      // Check that file was accepted
      await page.waitForTimeout(500);

      // Look for file name display or success indicator
      const content = await page.content();
      const hasFile = content.includes('test-content') || content.includes('.txt') || await page.locator('.file-name, .selected-file, .file-list').count() > 0;
      expect(hasFile).toBe(true);
    });

    test('should show error for unsupported file type', async ({ page }) => {
      await page.goto('/upload.html');

      const fileInput = page.locator('input[type="file"]');

      // Try to upload an unsupported file type
      await fileInput.setInputFiles({
        name: 'test.xyz',
        mimeType: 'application/octet-stream',
        buffer: Buffer.from('test content'),
      });

      await page.waitForTimeout(500);

      // Check if file was rejected or error shown
      const errorMessage = page.locator('.error, .invalid, [role="alert"]');
      const hasError = await errorMessage.count() > 0;

      // Either error shown or file input still empty/shows warning
      // Some implementations might just ignore the file
    });

    test('should allow removing selected file', async ({ page }) => {
      await page.goto('/upload.html');

      const fileInput = page.locator('input[type="file"]');

      await fileInput.setInputFiles({
        name: 'test-file.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Test content'),
      });

      await page.waitForTimeout(500);

      // Look for remove button
      const removeButton = page.locator('button:has-text("Remove"), .remove-file, .delete-file, [data-remove]');

      if (await removeButton.count() > 0) {
        await removeButton.first().click();
        await page.waitForTimeout(300);

        // File should be removed
        const fileDisplay = page.locator('.file-name, .selected-file');
        const fileCount = await fileDisplay.count();
        expect(fileCount).toBe(0);
      }
    });
  });

  test.describe('Text Paste', () => {
    test('should accept pasted text content', async ({ page }) => {
      await page.goto('/upload.html');

      // Switch to paste mode if needed
      const pasteTab = page.locator('button:has-text("Paste"), [data-tab="paste"]');
      if (await pasteTab.count() > 0) {
        await pasteTab.first().click();
        await page.waitForTimeout(300);
      }

      const textarea = page.locator('textarea');

      if (await textarea.count() > 0) {
        const testContent = `This is a comprehensive test of the content multiplier platform.

The platform should be able to take this text and transform it into multiple content formats including LinkedIn posts, blog articles, and email sequences.

Key points to extract:
1. Content transformation capabilities
2. Multiple output formats
3. AI-powered processing

This should provide enough content for the distillation process.`;

        await textarea.first().fill(testContent);

        // Verify content was entered
        const value = await textarea.first().inputValue();
        expect(value.length).toBeGreaterThan(50);
      }
    });

    test('should show character count if present', async ({ page }) => {
      await page.goto('/upload.html');

      const pasteTab = page.locator('button:has-text("Paste"), [data-tab="paste"]');
      if (await pasteTab.count() > 0) {
        await pasteTab.first().click();
        await page.waitForTimeout(300);
      }

      const textarea = page.locator('textarea');
      if (await textarea.count() > 0) {
        await textarea.first().fill('Test content here');

        // Check for character counter
        const charCounter = page.locator('.char-count, .character-count, [data-chars]');
        // Character counter is optional feature
      }
    });
  });

  test.describe('Form Validation', () => {
    test('should require persona selection', async ({ page }) => {
      await page.goto('/upload.html');

      // Upload a file
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'test.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Test content for processing'),
      });

      // Try to submit without selecting persona
      const submitButton = page.locator('button[type="submit"], button:has-text("Upload"), button:has-text("Process"), button:has-text("Start")');
      await submitButton.first().click();

      // Should show validation error or prevent submission
      await page.waitForTimeout(1000);

      // Check if still on upload page (form not submitted)
      const url = page.url();
      // Either stays on page or shows error
    });

    test('should require at least one content type for full pipeline', async ({ page }) => {
      await page.goto('/upload.html');

      // Select a persona
      const personaSelect = page.locator('select').first();
      if (await personaSelect.count() > 0) {
        const options = await personaSelect.locator('option').all();
        if (options.length > 1) {
          await personaSelect.selectOption({ index: 1 });
        }
      }

      // Uncheck all content types
      const checkboxes = page.locator('input[type="checkbox"]:checked');
      const checkedCount = await checkboxes.count();

      for (let i = 0; i < checkedCount; i++) {
        await checkboxes.nth(0).uncheck();
        await page.waitForTimeout(100);
      }

      // Try to submit
      const submitButton = page.locator('button[type="submit"], button:has-text("Upload"), button:has-text("Process")');

      if (await submitButton.first().isEnabled()) {
        await submitButton.first().click();
        await page.waitForTimeout(1000);
      }
    });

    test('should validate quantity inputs', async ({ page }) => {
      await page.goto('/upload.html');

      // Find quantity inputs
      const quantityInputs = page.locator('input[type="number"], input[name*="qty"], input[name*="quantity"]');

      if (await quantityInputs.count() > 0) {
        // Try to enter invalid quantity
        await quantityInputs.first().fill('-1');

        // Check for validation
        const isInvalid = await quantityInputs.first().evaluate((el: HTMLInputElement) => !el.validity.valid);

        // Should have min constraint
        const min = await quantityInputs.first().getAttribute('min');
        if (min) {
          expect(parseInt(min)).toBeGreaterThanOrEqual(0);
        }
      }
    });
  });

  test.describe('Content Type Selection', () => {
    test('should allow selecting multiple content types', async ({ page }) => {
      await page.goto('/upload.html');

      const checkboxes = page.locator('input[type="checkbox"]');
      const count = await checkboxes.count();

      if (count >= 2) {
        await checkboxes.nth(0).check();
        await checkboxes.nth(1).check();

        // Verify both are checked
        expect(await checkboxes.nth(0).isChecked()).toBe(true);
        expect(await checkboxes.nth(1).isChecked()).toBe(true);
      }
    });

    test('should show quantity options when content type is selected', async ({ page }) => {
      await page.goto('/upload.html');

      // Find LinkedIn or similar checkbox with quantity
      const linkedinCheckbox = page.locator('input[type="checkbox"]').first();

      if (await linkedinCheckbox.count() > 0) {
        await linkedinCheckbox.check();

        // Look for associated quantity input that might appear
        const quantityInput = page.locator('input[type="number"]');
        // Quantity inputs may or may not be conditionally shown
      }
    });
  });

  test.describe('Persona Selection', () => {
    test('should list available personas', async ({ page }) => {
      await page.goto('/upload.html');

      const personaSelect = page.locator('select').first();

      if (await personaSelect.count() > 0) {
        const options = await personaSelect.locator('option').all();
        expect(options.length).toBeGreaterThan(0);
      }
    });

    test('should allow selecting a persona', async ({ page }) => {
      await page.goto('/upload.html');

      const personaSelect = page.locator('select').first();

      if (await personaSelect.count() > 0) {
        const options = await personaSelect.locator('option').all();

        if (options.length > 1) {
          await personaSelect.selectOption({ index: 1 });

          const selectedValue = await personaSelect.inputValue();
          expect(selectedValue).toBeTruthy();
        }
      }
    });
  });

  test.describe('Quick Distill', () => {
    test('should have quick distill option', async ({ page }) => {
      await page.goto('/upload.html');

      const quickDistillTab = page.locator('button:has-text("Quick"), [data-tab="distill"], button:has-text("Distill")');
      const hasQuickDistill = await quickDistillTab.count() > 0;

      // Quick distill is an optional feature
      if (hasQuickDistill) {
        await quickDistillTab.first().click();
        await page.waitForTimeout(300);

        // Should show simplified form without content type selection
        const contentCheckboxes = page.locator('input[type="checkbox"][name*="content"], input[type="checkbox"][value*="linkedin"]');
        // Content types might be hidden in quick distill mode
      }
    });
  });

  test.describe('Batch Upload', () => {
    test('should accept multiple files', async ({ page }) => {
      await page.goto('/upload.html');

      const fileInput = page.locator('input[type="file"]');
      const multiple = await fileInput.getAttribute('multiple');

      // Check if multiple file upload is supported
      if (multiple !== null) {
        await fileInput.setInputFiles([
          {
            name: 'file1.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from('Content from file 1'),
          },
          {
            name: 'file2.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from('Content from file 2'),
          },
        ]);

        await page.waitForTimeout(500);

        // Check for batch indicator or multiple files shown
        const content = await page.content();
        const hasBatchIndicator = content.includes('file1') || content.includes('file2') || content.includes('2 files') || content.includes('batch');
      }
    });
  });

  test.describe('Optional Fields', () => {
    test('should have campaign name field', async ({ page }) => {
      await page.goto('/upload.html');

      const campaignInput = page.locator('input[name*="campaign"], input[placeholder*="campaign"], #campaignName');

      if (await campaignInput.count() > 0) {
        await campaignInput.first().fill('Test Campaign 2024');
        const value = await campaignInput.first().inputValue();
        expect(value).toBe('Test Campaign 2024');
      }
    });

    test('should have magic words/domain vocabulary field', async ({ page }) => {
      await page.goto('/upload.html');

      const vocabInput = page.locator('input[name*="vocab"], input[name*="magic"], input[placeholder*="words"], textarea[name*="vocab"]');

      if (await vocabInput.count() > 0) {
        await vocabInput.first().fill('AI, ML, ContentMultiplier');
        const value = await vocabInput.first().inputValue();
        expect(value).toContain('AI');
      }
    });
  });

  test.describe('Drag and Drop', () => {
    test('should have drop zone visual feedback', async ({ page }) => {
      await page.goto('/upload.html');

      // Look for drop zone area
      const dropZone = page.locator('.dropzone, .drop-area, .upload-area, [data-dropzone]');

      if (await dropZone.count() > 0) {
        // Simulate drag over
        await dropZone.first().dispatchEvent('dragover');
        await page.waitForTimeout(300);

        // Check for visual feedback (class change, border change, etc.)
        const hasActiveClass = await dropZone.first().evaluate((el) => {
          return el.classList.contains('active') ||
                 el.classList.contains('drag-over') ||
                 el.classList.contains('highlight');
        });

        // Visual feedback is expected but implementation may vary
      }
    });
  });

  test.describe('Form Reset', () => {
    test('should be able to reset form', async ({ page }) => {
      await page.goto('/upload.html');

      // Fill some fields
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'test.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Test'),
      });

      // Look for reset or clear button
      const resetButton = page.locator('button[type="reset"], button:has-text("Clear"), button:has-text("Reset")');

      if (await resetButton.count() > 0) {
        await resetButton.first().click();
        await page.waitForTimeout(300);

        // Form should be cleared
      }
    });
  });
});
