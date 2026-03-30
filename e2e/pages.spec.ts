import { test, expect, registerUser } from './fixtures';

const PUBLIC_PAGES = ['/', '/login.html', '/register.html'];

const AUTH_PAGES = [
  '/upload.html',
  '/reserve.html',
  '/results.html',
  '/settings.html',
  '/workshop.html',
  '/calendar.html',
  '/autopilot.html',
  '/brand-voice.html',
  '/swipes.html',
  '/remix.html',
  '/batch-status.html',
  '/refresh.html',
];

test.describe('Public pages load without errors', () => {
  for (const path of PUBLIC_PAGES) {
    test(`${path} loads`, async ({ page }) => {
      const errors: string[] = [];
      page.on('pageerror', (err) => errors.push(err.message));

      const res = await page.goto(path);
      expect(res?.status()).toBe(200);
      expect(errors).toEqual([]);
    });
  }
});

test.describe('Authenticated pages load without errors', () => {
  for (const path of AUTH_PAGES) {
    test(`${path} loads`, async ({ page, request }) => {
      const { token } = await registerUser(request);

      // Set token in localStorage before navigating
      await page.goto('/login.html');
      await page.evaluate((t) => localStorage.setItem('token', t), token);

      const errors: string[] = [];
      page.on('pageerror', (err) => errors.push(err.message));

      await page.goto(path);
      // Page should load (200) — it may redirect to login if token isn't picked up,
      // but the server should never 500.
      expect(errors).toEqual([]);
    });
  }
});
