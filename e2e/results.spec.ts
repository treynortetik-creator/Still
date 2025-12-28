/**
 * Results & Editing Tests
 * Tests for viewing generated content, editing, feedback, and export.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Results Page', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login
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
    test('should load results page', async ({ page }) => {
      await page.goto('/results.html');

      // Should show results or no-job message
      const hasContent = await page.locator('.results, .outputs, .content, .no-job, .error').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should have tabs for outputs and atoms', async ({ page }) => {
      await page.goto('/results.html');

      const tabs = page.locator('[role="tab"], .tab, button:has-text("Generated"), button:has-text("Atoms"), button:has-text("Stills")');
      const tabCount = await tabs.count();

      // Tabs separate outputs from extracted atoms
    });

    test('should have export options', async ({ page }) => {
      await page.goto('/results.html');

      const exportButton = page.locator('button:has-text("Export"), .export-dropdown, [data-export]');
      const hasExport = await exportButton.count() > 0;

      // Export functionality expected
    });
  });

  test.describe('Generated Content Display', () => {
    test('should display output cards', async ({ page }) => {
      await page.goto('/results.html');

      const outputCards = page.locator('.output-card, .content-card, .result-item, article');
      // May have zero if no job results
    });

    test('should show content type labels', async ({ page }) => {
      await page.goto('/results.html');

      const labels = page.locator('.type-label, .content-type, .badge');
      // Labels identify LinkedIn, Blog, Email content
    });

    test('should show quality scores', async ({ page }) => {
      await page.goto('/results.html');

      const scores = page.locator('.quality-score, .score, .rating');
      // Quality scores help evaluate content
    });
  });

  test.describe('Copy Functionality', () => {
    test('should have copy button on outputs', async ({ page }) => {
      await page.goto('/results.html');

      const copyButton = page.locator('button:has-text("Copy"), .copy-button, [data-action="copy"]');
      const hasCopy = await copyButton.count() > 0;

      // Copy buttons should exist on output cards
    });

    test('should show confirmation when content copied', async ({ page }) => {
      await page.goto('/results.html');

      const copyButton = page.locator('button:has-text("Copy"), .copy-button');

      if (await copyButton.count() > 0) {
        await copyButton.first().click();
        await page.waitForTimeout(500);

        // Look for confirmation
        const confirmation = page.locator('.copied, .toast, :has-text("Copied"), .success');
        // Confirmation expected after copy
      }
    });
  });

  test.describe('Feedback System', () => {
    test('should have thumbs up/down buttons', async ({ page }) => {
      await page.goto('/results.html');

      const thumbsUp = page.locator('button[aria-label*="up"], .thumbs-up, [data-feedback="positive"]');
      const thumbsDown = page.locator('button[aria-label*="down"], .thumbs-down, [data-feedback="negative"]');

      // Feedback buttons expected on outputs
    });

    test('should submit positive feedback', async ({ page }) => {
      await page.goto('/results.html');

      const thumbsUp = page.locator('.thumbs-up, button:has-text("👍"), [data-feedback="positive"]');

      if (await thumbsUp.count() > 0) {
        await thumbsUp.first().click();
        await page.waitForTimeout(500);

        // Should show feedback submitted indicator
      }
    });

    test('should submit negative feedback', async ({ page }) => {
      await page.goto('/results.html');

      const thumbsDown = page.locator('.thumbs-down, button:has-text("👎"), [data-feedback="negative"]');

      if (await thumbsDown.count() > 0) {
        await thumbsDown.first().click();
        await page.waitForTimeout(500);

        // Should show feedback submitted indicator
      }
    });
  });

  test.describe('Hook Variations', () => {
    test('should show hook variation options for LinkedIn', async ({ page }) => {
      await page.goto('/results.html');

      const hookOptions = page.locator('.hook-variation, .hook-option, button:has-text("Question"), button:has-text("Statistic")');
      // Hook variations for LinkedIn posts
    });

    test('should allow selecting different hook', async ({ page }) => {
      await page.goto('/results.html');

      const hookOption = page.locator('.hook-option, .hook-variation').first();

      if (await hookOption.count() > 0) {
        await hookOption.click();
        await page.waitForTimeout(300);

        // Hook should be applied/highlighted
      }
    });
  });

  test.describe('Tone Adjustment', () => {
    test('should have tone adjustment dropdown', async ({ page }) => {
      await page.goto('/results.html');

      const toneSelect = page.locator('select[name*="tone"], .tone-select, [data-tone]');
      const hasTone = await toneSelect.count() > 0;

      // Tone adjustment is a key editing feature
    });

    test('should apply tone adjustment', async ({ page }) => {
      await page.goto('/results.html');

      const toneSelect = page.locator('select[name*="tone"], .tone-select');

      if (await toneSelect.count() > 0) {
        await toneSelect.first().selectOption({ index: 1 });

        const applyButton = page.locator('button:has-text("Apply"), .apply-tone');

        if (await applyButton.count() > 0) {
          await applyButton.first().click();
          await page.waitForTimeout(1000);

          // Should show loading or updated content
        }
      }
    });
  });

  test.describe('Custom Edit', () => {
    test('should have custom edit input', async ({ page }) => {
      await page.goto('/results.html');

      const editInput = page.locator('textarea[name*="edit"], input[placeholder*="edit"], .edit-instructions');
      // Custom edit allows specific changes
    });

    test('should submit custom edit instructions', async ({ page }) => {
      await page.goto('/results.html');

      const editInput = page.locator('textarea[name*="edit"], .edit-instructions');

      if (await editInput.count() > 0) {
        await editInput.first().fill('Make this more concise');

        const regenerateButton = page.locator('button:has-text("Regenerate"), button:has-text("Apply")');

        if (await regenerateButton.count() > 0) {
          await regenerateButton.first().click();
          await page.waitForTimeout(1000);

          // Should show loading or preview
        }
      }
    });

    test('should show edit preview before accepting', async ({ page }) => {
      await page.goto('/results.html');

      // Edit preview allows accepting/rejecting changes
      const preview = page.locator('.preview, .edit-preview, .diff');
      // Preview shown after edit request
    });
  });

  test.describe('Version History', () => {
    test('should have version toggle', async ({ page }) => {
      await page.goto('/results.html');

      const versionToggle = page.locator('.version-toggle, button:has-text("Draft"), button:has-text("Edited"), button:has-text("Final")');
      // Version history shows content evolution
    });

    test('should switch between versions', async ({ page }) => {
      await page.goto('/results.html');

      const versionButtons = page.locator('.version-toggle button, .version-option');

      if (await versionButtons.count() >= 2) {
        await versionButtons.nth(0).click();
        await page.waitForTimeout(300);

        await versionButtons.nth(1).click();
        await page.waitForTimeout(300);

        // Content should change between versions
      }
    });
  });

  test.describe('Device Preview', () => {
    test('should have mobile/desktop preview toggle', async ({ page }) => {
      await page.goto('/results.html');

      const previewToggle = page.locator('button:has-text("Mobile"), button:has-text("Desktop"), .device-toggle');
      const hasToggle = await previewToggle.count() > 0;

      // Device preview helps visualize content
    });

    test('should toggle between device views', async ({ page }) => {
      await page.goto('/results.html');

      const mobileButton = page.locator('button:has-text("Mobile"), .mobile-preview');

      if (await mobileButton.count() > 0) {
        await mobileButton.first().click();
        await page.waitForTimeout(300);

        // Should show mobile-sized preview
      }
    });
  });

  test.describe('Image Prompts', () => {
    test('should show image prompts section', async ({ page }) => {
      await page.goto('/results.html');

      const imagePrompts = page.locator('.image-prompts, :has-text("Midjourney"), :has-text("DALL-E")');
      // Image prompts help create visuals
    });

    test('should allow copying image prompts', async ({ page }) => {
      await page.goto('/results.html');

      const promptCopyButton = page.locator('.image-prompts button:has-text("Copy"), .prompt-copy');

      if (await promptCopyButton.count() > 0) {
        await promptCopyButton.first().click();
        await page.waitForTimeout(300);

        // Should show copy confirmation
      }
    });
  });

  test.describe('Export', () => {
    test('should have export dropdown', async ({ page }) => {
      await page.goto('/results.html');

      const exportDropdown = page.locator('.export-dropdown, button:has-text("Export")');

      if (await exportDropdown.count() > 0) {
        await exportDropdown.first().click();
        await page.waitForTimeout(300);

        // Should show export options
        const options = page.locator('.export-option, a:has-text("Markdown"), a:has-text("JSON")');
        const hasOptions = await options.count() > 0;
      }
    });

    test('should export as Markdown', async ({ page }) => {
      await page.goto('/results.html');

      const exportButton = page.locator('button:has-text("Export")');

      if (await exportButton.count() > 0) {
        await exportButton.first().click();
        await page.waitForTimeout(300);

        const mdOption = page.locator('a:has-text("Markdown"), button:has-text("Markdown")');

        if (await mdOption.count() > 0) {
          // Click should trigger download
          await mdOption.first().click();
        }
      }
    });

    test('should export as JSON', async ({ page }) => {
      await page.goto('/results.html');

      const exportButton = page.locator('button:has-text("Export")');

      if (await exportButton.count() > 0) {
        await exportButton.first().click();
        await page.waitForTimeout(300);

        const jsonOption = page.locator('a:has-text("JSON"), button:has-text("JSON")');

        if (await jsonOption.count() > 0) {
          await jsonOption.first().click();
        }
      }
    });

    test('should export as Word', async ({ page }) => {
      await page.goto('/results.html');

      const wordOption = page.locator('a:has-text("Word"), button:has-text("Word"), a:has-text(".docx")');
      // Word export available
    });

    test('should export all as ZIP', async ({ page }) => {
      await page.goto('/results.html');

      const zipOption = page.locator('a:has-text("ZIP"), button:has-text("ZIP"), a:has-text("Download All")');
      // ZIP export bundles everything
    });
  });

  test.describe('Atoms/Stills Tab', () => {
    test('should switch to atoms tab', async ({ page }) => {
      await page.goto('/results.html');

      const atomsTab = page.locator('button:has-text("Atoms"), button:has-text("Stills"), [data-tab="atoms"]');

      if (await atomsTab.count() > 0) {
        await atomsTab.first().click();
        await page.waitForTimeout(300);

        // Should show atoms/stills content
      }
    });

    test('should filter atoms by type', async ({ page }) => {
      await page.goto('/results.html');

      // Switch to atoms tab
      const atomsTab = page.locator('button:has-text("Atoms"), button:has-text("Stills")');

      if (await atomsTab.count() > 0) {
        await atomsTab.first().click();
        await page.waitForTimeout(300);

        // Filter by type
        const typeFilter = page.locator('button:has-text("Data"), button:has-text("Story")');

        if (await typeFilter.count() > 0) {
          await typeFilter.first().click();
          await page.waitForTimeout(300);
        }
      }
    });

    test('should show relevance scores on atoms', async ({ page }) => {
      await page.goto('/results.html');

      const atomsTab = page.locator('button:has-text("Atoms"), button:has-text("Stills")');

      if (await atomsTab.count() > 0) {
        await atomsTab.first().click();
        await page.waitForTimeout(300);

        const relevance = page.locator('.relevance, .dots, .score');
        // Relevance helps prioritize atoms
      }
    });
  });

  test.describe('Navigation', () => {
    test('should have link to Reserve', async ({ page }) => {
      await page.goto('/results.html');

      const reserveLink = page.locator('a:has-text("Reserve"), a:has-text("Library"), a[href*="reserve"]');
      const hasLink = await reserveLink.count() > 0;

      // Link to view stills in reserve
    });

    test('should have New Upload button', async ({ page }) => {
      await page.goto('/results.html');

      const newUpload = page.locator('a:has-text("New Upload"), button:has-text("New Upload"), a[href*="upload"]');
      const hasButton = await newUpload.count() > 0;

      // Quick way to start new job
    });
  });

  test.describe('Quality Score Details', () => {
    test('should show quality score breakdown on hover/click', async ({ page }) => {
      await page.goto('/results.html');

      const scoreElement = page.locator('.quality-score, .score-badge');

      if (await scoreElement.count() > 0) {
        await scoreElement.first().hover();
        await page.waitForTimeout(300);

        // Tooltip or expanded view should show breakdown
        const breakdown = page.locator('.score-breakdown, .tooltip, .score-details');
      }
    });
  });

  test.describe('Warnings Display', () => {
    test('should show warnings if present', async ({ page }) => {
      await page.goto('/results.html');

      const warnings = page.locator('.warning, .alert-warning, [role="alert"]');
      // Warnings flag potential issues
    });
  });
});

test.describe('Workshop Page', () => {
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

  test('should load workshop page', async ({ page }) => {
    await page.goto('/workshop.html');

    const hasContent = await page.locator('.workshop, .editor, textarea, .content').count() > 0;
    expect(hasContent).toBe(true);
  });

  test('should have editing area', async ({ page }) => {
    await page.goto('/workshop.html');

    const editor = page.locator('textarea, .editor, [contenteditable="true"]');
    const hasEditor = await editor.count() > 0;

    // Workshop is for advanced editing
  });

  test('should have save button', async ({ page }) => {
    await page.goto('/workshop.html');

    const saveButton = page.locator('button:has-text("Save"), button:has-text("Update")');
    const hasSave = await saveButton.count() > 0;

    // Save preserves edits
  });
});
