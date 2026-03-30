import { test, expect } from './fixtures';

test.describe('Health & basics', () => {
  test('GET /health returns healthy', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('healthy');
  });

  test('GET /api returns app info', async ({ request }) => {
    const res = await request.get('/api');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.name).toBe('ContentMultiplier API');
    expect(body.status).toBe('running');
  });

  test('homepage loads', async ({ page }) => {
    const res = await page.goto('/');
    expect(res?.status()).toBe(200);
  });

  test('login page loads', async ({ page }) => {
    const res = await page.goto('/login.html');
    expect(res?.status()).toBe(200);
  });

  test('register page loads', async ({ page }) => {
    const res = await page.goto('/register.html');
    expect(res?.status()).toBe(200);
  });
});
