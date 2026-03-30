import { test as base, expect, type APIRequestContext } from '@playwright/test';

export const TEST_PASSWORD = 'TestPassword1';

export function uniqueEmail(): string {
  return `test-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

/** Register a new user via the API and return the auth token. */
export async function registerUser(
  request: APIRequestContext,
  email?: string,
): Promise<{ token: string; email: string }> {
  const e = email ?? uniqueEmail();
  const res = await request.post('/api/auth/register', {
    data: { email: e, password: TEST_PASSWORD, confirm_password: TEST_PASSWORD },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  return { token: body.access_token, email: e };
}

export { base as test, expect };
