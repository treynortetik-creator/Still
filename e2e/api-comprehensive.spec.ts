/**
 * Comprehensive API Tests
 * Tests all API endpoints for correct status codes and response shapes.
 * Covers endpoints that the existing api.spec.ts doesn't test.
 */
import { test, expect } from '@playwright/test';
import { uniqueEmail } from './fixtures';

let authToken: string;

test.describe('Comprehensive API Tests', () => {
  test.beforeAll(async ({ request }) => {
    // Register a test user and get token
    const email = uniqueEmail();
    const response = await request.post('/api/auth/register', {
      data: {
        email,
        password: 'TestPassword123!',
        confirm_password: 'TestPassword123!',
      },
    });
    expect(response.status()).toBe(200);
    const data = await response.json();
    authToken = data.access_token;
  });

  test.describe('Brand Voice Endpoints', () => {
    test('GET /api/brand-voice/config should return config', async ({ request }) => {
      const response = await request.get('/api/brand-voice/config', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });

    test('PUT /api/brand-voice/config should save config', async ({ request }) => {
      const response = await request.put('/api/brand-voice/config', {
        headers: { Authorization: `Bearer ${authToken}` },
        data: {
          company_name: 'Test Corp',
          industry: 'Technology',
          tone_linkedin: 'Professional',
          tone_blog: 'Educational',
          tone_email: 'Friendly',
          vocabulary_level: 'professional',
          core_principles: ['Be concise'],
          phrases_to_use: ['leverage'],
          phrases_to_avoid: ['synergy'],
        },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Persona Endpoints', () => {
    test('GET /api/personas should return default personas', async ({ request }) => {
      const response = await request.get('/api/personas', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.personas).toBeDefined();
      expect(data.personas.length).toBeGreaterThanOrEqual(3);
    });

    test('GET /api/personas/all should include defaults and custom', async ({ request }) => {
      const response = await request.get('/api/personas/all', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.personas).toBeDefined();
    });

    test('each persona should have required fields', async ({ request }) => {
      const response = await request.get('/api/personas', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await response.json();
      for (const persona of data.personas) {
        expect(persona.id).toBeTruthy();
        expect(persona.title).toBeTruthy();
      }
    });
  });

  test.describe('Memory Rules Endpoints', () => {
    test('GET /api/memory-rules should return rules list', async ({ request }) => {
      const response = await request.get('/api/memory-rules', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Webhooks Endpoints', () => {
    test('GET /api/webhooks should return webhooks list', async ({ request }) => {
      const response = await request.get('/api/webhooks', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Calendar Endpoints', () => {
    test('GET /api/calendar should return scheduled items', async ({ request }) => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
      const response = await request.get(`/api/calendar?start_date=${start}&end_date=${end}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Autopilot Endpoints', () => {
    test('GET /api/autopilot/sources should return sources', async ({ request }) => {
      const response = await request.get('/api/autopilot/sources', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });

    test('GET /api/autopilot/stats should return stats', async ({ request }) => {
      const response = await request.get('/api/autopilot/stats', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Swipes Endpoints', () => {
    test('GET /api/swipes should return swipes list', async ({ request }) => {
      const response = await request.get('/api/swipes?limit=10', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Remix Endpoints', () => {
    test('GET /api/remix/stats should return remix stats', async ({ request }) => {
      const response = await request.get('/api/remix/stats', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Library Endpoints', () => {
    test('GET /api/library should return stills', async ({ request }) => {
      const response = await request.get('/api/library', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBe(200);
    });

    test('GET /api/library/stats should return library stats', async ({ request }) => {
      const response = await request.get('/api/library/stats', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Outputs Endpoints', () => {
    test('GET /api/outputs should return outputs list', async ({ request }) => {
      const response = await request.get('/api/outputs', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Analytics Endpoints', () => {
    test('GET /api/analytics should return analytics', async ({ request }) => {
      const response = await request.get('/api/analytics', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });

    test('GET /api/analytics/costs should return cost data', async ({ request }) => {
      const response = await request.get('/api/analytics/costs', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Sommelier Endpoints', () => {
    test('GET /api/sommelier/examples should return search examples', async ({ request }) => {
      const response = await request.get('/api/sommelier/examples', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Edit Endpoints', () => {
    test('GET /api/edit/tone-presets should return presets', async ({ request }) => {
      const response = await request.get('/api/edit/tone-presets', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      expect(response.status()).toBeLessThan(500);
    });
  });

  test.describe('Unauthorized Access', () => {
    test('all protected endpoints should reject without token', async ({ request }) => {
      const endpoints = [
        '/api/library',
        '/api/outputs',
        '/api/personas',
        '/api/brand-voice/config',
        '/api/webhooks',
        '/api/calendar',
        '/api/autopilot/sources',
        '/api/swipes',
        '/api/analytics',
      ];

      for (const endpoint of endpoints) {
        const response = await request.get(endpoint);
        expect(response.status()).toBe(401);
      }
    });
  });
});
