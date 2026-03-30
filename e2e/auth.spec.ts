import { test, expect, registerUser, uniqueEmail, TEST_PASSWORD } from './fixtures';

test.describe('Auth API', () => {
  test('register → login → me → logout', async ({ request }) => {
    const email = uniqueEmail();

    // Register
    const reg = await request.post('/api/auth/register', {
      data: { email, password: TEST_PASSWORD, confirm_password: TEST_PASSWORD },
    });
    expect(reg.status()).toBe(200);
    const regBody = await reg.json();
    expect(regBody.access_token).toBeTruthy();
    const token = regBody.access_token;

    // /me with valid token
    const me = await request.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(me.status()).toBe(200);
    const meBody = await me.json();
    expect(meBody.email).toBe(email);

    // Login with same creds
    const login = await request.post('/api/auth/login', {
      headers: { 'X-Forwarded-For': uniqueEmail() },
      data: { email, password: TEST_PASSWORD },
    });
    expect(login.status()).toBe(200);
    const loginBody = await login.json();
    expect(loginBody.access_token).toBeTruthy();

    // Logout
    const logout = await request.post('/api/auth/logout', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(logout.status()).toBe(200);
  });

  test('register rejects weak password', async ({ request }) => {
    const res = await request.post('/api/auth/register', {
      data: { email: uniqueEmail(), password: 'short', confirm_password: 'short' },
    });
    expect(res.status()).toBe(400);
  });

  test('register rejects mismatched passwords', async ({ request }) => {
    const res = await request.post('/api/auth/register', {
      data: { email: uniqueEmail(), password: TEST_PASSWORD, confirm_password: 'Different1' },
    });
    expect(res.status()).toBe(400);
  });

  test('register rejects duplicate email', async ({ request }) => {
    const email = uniqueEmail();
    await request.post('/api/auth/register', {
      data: { email, password: TEST_PASSWORD, confirm_password: TEST_PASSWORD },
    });
    const dup = await request.post('/api/auth/register', {
      data: { email, password: TEST_PASSWORD, confirm_password: TEST_PASSWORD },
    });
    expect(dup.status()).toBe(400);
  });

  test('login rejects wrong password', async ({ request }) => {
    const { email } = await registerUser(request);
    const res = await request.post('/api/auth/login', {
      headers: { 'X-Forwarded-For': uniqueEmail() },
      data: { email, password: 'WrongPassword1' },
    });
    expect(res.status()).toBe(401);
  });

  test('/me rejects missing token', async ({ request }) => {
    const res = await request.get('/api/auth/me');
    expect(res.status()).toBe(401);
  });

  test('/me rejects invalid token', async ({ request }) => {
    const res = await request.get('/api/auth/me', {
      headers: { Authorization: 'Bearer garbage.token.here' },
    });
    expect(res.status()).toBe(401);
  });
});
