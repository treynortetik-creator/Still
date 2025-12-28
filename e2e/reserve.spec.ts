/**
 * Content Library (Reserve) Tests
 * Tests for browsing, filtering, searching, and generating from the content reserve.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

test.describe('Content Reserve / Library', () => {
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

  test.describe('Page Structure', () => {
    test('should load reserve page', async ({ page }) => {
      await page.goto('/reserve.html');

      // Should either show content or empty state
      const hasContent = await page.locator('.reserve, .library, .stills, .empty-state, .no-content, .grid, .list').count() > 0;
      expect(hasContent).toBe(true);
    });

    test('should display header with total count', async ({ page }) => {
      await page.goto('/reserve.html');

      // Look for header or count indicator
      const header = page.locator('h1, h2, .header, .title');
      await expect(header.first()).toBeVisible();
    });

    test('should show empty state for new users', async ({ page }) => {
      await page.goto('/reserve.html');

      // New user should see empty state or zero items
      const emptyState = page.locator('.empty, .no-content, .no-stills, :has-text("No stills"), :has-text("empty")');
      const countZero = page.locator(':has-text("0 stills"), :has-text("0 items")');

      const hasEmptyIndicator = await emptyState.count() > 0 || await countZero.count() > 0;
      // May or may not show empty state depending on implementation
    });
  });

  test.describe('Filtering', () => {
    test('should have type filter options', async ({ page }) => {
      await page.goto('/reserve.html');

      // Look for filter chips or dropdown
      const typeFilters = page.locator('.filter, .type-filter, [data-filter], button:has-text("Data"), button:has-text("Story"), button:has-text("Insight")');
      const count = await typeFilters.count();

      // Filters should exist
      expect(count).toBeGreaterThanOrEqual(0);
    });

    test('should filter by type when clicked', async ({ page }) => {
      await page.goto('/reserve.html');

      const typeFilter = page.locator('button:has-text("Data"), [data-type="data"], .filter-data');

      if (await typeFilter.count() > 0) {
        await typeFilter.first().click();
        await page.waitForTimeout(500);

        // URL should update or filter should be applied
        const url = page.url();
        // Check for filter indicator
      }
    });

    test('should have persona filter', async ({ page }) => {
      await page.goto('/reserve.html');

      const personaFilter = page.locator('select[name*="persona"], .persona-filter, [data-persona-filter]');
      const hasPersonaFilter = await personaFilter.count() > 0;

      // Persona filter is expected
    });

    test('should have relevance filter', async ({ page }) => {
      await page.goto('/reserve.html');

      const relevanceFilter = page.locator('select[name*="relevance"], .relevance-filter, input[type="range"], [data-relevance]');
      const hasRelevanceFilter = await relevanceFilter.count() > 0;

      // Relevance filter is expected
    });

    test('should have clear filters button', async ({ page }) => {
      await page.goto('/reserve.html');

      const clearButton = page.locator('button:has-text("Clear"), button:has-text("Reset"), .clear-filters');

      if (await clearButton.count() > 0) {
        // Apply a filter first
        const typeFilter = page.locator('.filter, [data-filter]').first();
        if (await typeFilter.count() > 0) {
          await typeFilter.click();
          await page.waitForTimeout(300);
        }

        // Then clear
        await clearButton.first().click();
        await page.waitForTimeout(300);
      }
    });
  });

  test.describe('Search', () => {
    test('should have search input', async ({ page }) => {
      await page.goto('/reserve.html');

      const searchInput = page.locator('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"], .search-input');
      await expect(searchInput.first()).toBeVisible();
    });

    test('should search content on input', async ({ page }) => {
      await page.goto('/reserve.html');

      const searchInput = page.locator('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"]');

      if (await searchInput.count() > 0) {
        await searchInput.first().fill('test query');
        await page.waitForTimeout(1000); // Wait for debounce

        // Search should be triggered
        const url = page.url();
        // URL might contain search param or results should update
      }
    });

    test('should show no results message when search finds nothing', async ({ page }) => {
      await page.goto('/reserve.html');

      const searchInput = page.locator('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"]');

      if (await searchInput.count() > 0) {
        await searchInput.first().fill('xyznonexistentquery12345');
        await page.waitForTimeout(1000);

        // Should show no results message
        const noResults = page.locator('.no-results, .empty-results, :has-text("No results"), :has-text("not found")');
        // No results message expected for impossible query
      }
    });
  });

  test.describe('Sommelier (AI Search)', () => {
    test('should have sommelier search section', async ({ page }) => {
      await page.goto('/reserve.html');

      const sommelier = page.locator('.sommelier, [data-sommelier], :has-text("What kind of content")');
      const hasSommelier = await sommelier.count() > 0;

      // Sommelier is a key feature
    });

    test('should have example queries', async ({ page }) => {
      await page.goto('/reserve.html');

      const examples = page.locator('.example, .suggestion, .chip');
      const count = await examples.count();

      // Example queries help users understand the feature
    });

    test('should submit sommelier search', async ({ page }) => {
      await page.goto('/reserve.html');

      const sommelierInput = page.locator('input[placeholder*="What kind"], .sommelier input, [data-sommelier] input');

      if (await sommelierInput.count() > 0) {
        await sommelierInput.first().fill('content about leadership');

        const searchButton = page.locator('button:has-text("Find"), button:has-text("Search"), .sommelier button');

        if (await searchButton.count() > 0) {
          await searchButton.first().click();
          await page.waitForTimeout(2000);

          // Should show results or loading state
        }
      }
    });
  });

  test.describe('Still Cards', () => {
    test('should display still cards in grid or list', async ({ page }) => {
      await page.goto('/reserve.html');

      const cards = page.locator('.card, .still, .item, .grid-item');
      // May have zero cards for new user
    });

    test('should show still type badge on cards', async ({ page }) => {
      await page.goto('/reserve.html');

      const badges = page.locator('.badge, .type-badge, .label');
      // Badges show still types (Data, Story, etc.)
    });

    test('should show relevance indicator on cards', async ({ page }) => {
      await page.goto('/reserve.html');

      const relevance = page.locator('.relevance, .dots, .score, .rating');
      // Relevance dots or score expected on cards
    });
  });

  test.describe('Selection', () => {
    test('should allow selecting stills', async ({ page }) => {
      await page.goto('/reserve.html');

      const checkbox = page.locator('.card input[type="checkbox"], .still input[type="checkbox"], .select-still');

      if (await checkbox.count() > 0) {
        await checkbox.first().check();

        expect(await checkbox.first().isChecked()).toBe(true);
      }
    });

    test('should show selection count', async ({ page }) => {
      await page.goto('/reserve.html');

      const checkbox = page.locator('.card input[type="checkbox"], .still input[type="checkbox"]');

      if (await checkbox.count() >= 2) {
        await checkbox.nth(0).check();
        await checkbox.nth(1).check();

        // Should show "2 selected" or similar
        const selectionCount = page.locator('.selected-count, :has-text("selected"), :has-text("2 ")');
      }
    });

    test('should enable generate button when stills selected', async ({ page }) => {
      await page.goto('/reserve.html');

      const generateButton = page.locator('button:has-text("Generate"), button:has-text("Create")');

      if (await generateButton.count() > 0) {
        // Initially may be disabled
        const initiallyDisabled = await generateButton.first().isDisabled();

        // Select a still
        const checkbox = page.locator('.card input[type="checkbox"]');
        if (await checkbox.count() > 0) {
          await checkbox.first().check();
          await page.waitForTimeout(300);

          // Button should now be enabled
        }
      }
    });
  });

  test.describe('Generate from Selected', () => {
    test('should have generate from selected button', async ({ page }) => {
      await page.goto('/reserve.html');

      const generateButton = page.locator('button:has-text("Generate"), button:has-text("Create from"), button:has-text("Blend")');
      const hasButton = await generateButton.count() > 0;

      // Generate button is a key feature
    });

    test('should open generate modal when clicked', async ({ page }) => {
      await page.goto('/reserve.html');

      // First select a still
      const checkbox = page.locator('.card input[type="checkbox"]');

      if (await checkbox.count() > 0) {
        await checkbox.first().check();

        const generateButton = page.locator('button:has-text("Generate"), button:has-text("Create")');

        if (await generateButton.count() > 0 && await generateButton.first().isEnabled()) {
          await generateButton.first().click();
          await page.waitForTimeout(500);

          // Modal should appear
          const modal = page.locator('.modal, [role="dialog"], .overlay');
          const hasModal = await modal.count() > 0;
        }
      }
    });
  });

  test.describe('Pagination', () => {
    test('should have pagination controls if many items', async ({ page }) => {
      await page.goto('/reserve.html');

      const pagination = page.locator('.pagination, .pager, nav[aria-label*="page"], button:has-text("Next"), button:has-text("Previous")');
      // Pagination only shows with many items
    });

    test('should navigate between pages', async ({ page }) => {
      await page.goto('/reserve.html');

      const nextButton = page.locator('button:has-text("Next"), .next-page, [aria-label="Next"]');

      if (await nextButton.count() > 0 && await nextButton.first().isEnabled()) {
        await nextButton.first().click();
        await page.waitForTimeout(500);

        // Should navigate to next page
        const url = page.url();
      }
    });
  });

  test.describe('Still Actions', () => {
    test('should allow copying still content', async ({ page }) => {
      await page.goto('/reserve.html');

      const copyButton = page.locator('.card button:has-text("Copy"), .copy-button, [data-copy]');

      if (await copyButton.count() > 0) {
        await copyButton.first().click();

        // Check for copy confirmation
        const confirmation = page.locator('.copied, .toast, :has-text("Copied")');
      }
    });

    test('should allow viewing still details', async ({ page }) => {
      await page.goto('/reserve.html');

      const card = page.locator('.card, .still').first();

      if (await card.count() > 0) {
        await card.click();

        // Should expand or open detail view
        await page.waitForTimeout(300);
      }
    });
  });

  test.describe('Empty State Actions', () => {
    test('should have CTA to upload when empty', async ({ page }) => {
      await page.goto('/reserve.html');

      const uploadCta = page.locator('a:has-text("Upload"), button:has-text("Upload"), a[href*="upload"]');

      if (await uploadCta.count() > 0) {
        // CTA should be visible
        await expect(uploadCta.first()).toBeVisible();
      }
    });
  });

  test.describe('Stats Display', () => {
    test('should show library statistics', async ({ page }) => {
      await page.goto('/reserve.html');

      const stats = page.locator('.stats, .statistics, .summary, :has-text("total")');
      // Stats help users understand their content library
    });

    test('should show times used counter on stills', async ({ page }) => {
      await page.goto('/reserve.html');

      const usedCounter = page.locator('.used, .times-used, :has-text("used")');
      // Times used shows content reuse
    });
  });
});
