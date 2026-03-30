import { test, expect, registerUser } from './fixtures';

test.describe('Core API endpoints', () => {
  let token: string;

  test.beforeAll(async ({ request }) => {
    const user = await registerUser(request);
    token = user.token;
  });

  const headers = () => ({ Authorization: `Bearer ${token}` });

  test('GET /api/personas returns list', async ({ request }) => {
    const res = await request.get('/api/personas', { headers: headers() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/library returns object', async ({ request }) => {
    const res = await request.get('/api/library', { headers: headers() });
    expect(res.status()).toBe(200);
  });

  test('GET /api/jobs returns list', async ({ request }) => {
    const res = await request.get('/api/jobs', { headers: headers() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/brand-voice/config returns config', async ({ request }) => {
    const res = await request.get('/api/brand-voice/config', { headers: headers() });
    // 200 if config exists, 404 if not yet created — both are valid
    expect([200, 404]).toContain(res.status());
  });

  test('GET /api/calendar returns data', async ({ request }) => {
    const res = await request.get('/api/calendar?start=2026-01-01&end=2026-01-31', {
      headers: headers(),
    });
    expect(res.status()).toBe(200);
  });

  test('GET /api/memory-rules returns list', async ({ request }) => {
    const res = await request.get('/api/memory-rules', { headers: headers() });
    expect(res.status()).toBe(200);
  });

  test('GET /api/webhooks returns list', async ({ request }) => {
    const res = await request.get('/api/webhooks', { headers: headers() });
    expect(res.status()).toBe(200);
  });

  test('GET /api/edit/tone-presets returns presets', async ({ request }) => {
    const res = await request.get('/api/edit/tone-presets', { headers: headers() });
    expect(res.status()).toBe(200);
  });

  test('endpoints reject unauthenticated requests', async ({ request }) => {
    const endpoints = ['/api/personas', '/api/library', '/api/jobs'];
    for (const endpoint of endpoints) {
      const res = await request.get(endpoint);
      expect(res.status()).toBe(401);
    }
  });
});
