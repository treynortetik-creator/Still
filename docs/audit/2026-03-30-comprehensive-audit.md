# Still (ContentMultiplier) - Comprehensive Audit Report
**Date:** 2026-03-30
**Scope:** Full application audit - Backend, Frontend, Database, Security, Pipeline, Config/Deployment, Testing
**Audited by:** 7 parallel audit agents

---

## Executive Summary

Still has **deep foundational issues across every layer**. The most damaging problems are:

1. **Logout is broken** - Token blacklist isn't checked on 95% of endpoints, so logged-out tokens still work
2. **The content pipeline is massively over-engineered** - 18+ sequential AI calls per job when ~5-6 would suffice, and cost tracking always returns $0.00
3. **The test suite is non-functional** - conftest.py targets SQLite against a PostgreSQL-only app; ~7% route coverage
4. **The database schema file is dangerously out of sync** - fresh deploys from `supabase_schema.sql` produce a broken database
5. **Two pages are likely broken right now** - results.html and settings.html have ES6 module race conditions
6. **No mobile navigation** - navbar links are hidden on mobile with no hamburger menu
7. **~600+ lines of dead SQLite code** throughout the entire codebase

| Area | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Security & Auth | 3 | 7 | 9 | 7 | **26** |
| Pipeline & Services | 4 | 6 | 8 | 7 | **25** |
| Backend API & Routing | 3 | 5 | 7 | 9 | **24** |
| Database & SQL | 4 | 5 | 8 | 6 | **23** |
| Frontend & UX | 3 | 4 | 8 | 8 | **23** |
| Config & Deployment | 3 | 6 | 9 | 8 | **26** |
| Test Coverage | 6 | 5 | 7 | 5 | **23** |
| **TOTAL** | **26** | **38** | **56** | **50** | **170** |

---

## CRITICAL FINDINGS (26)

### Security

**SEC-C1. `get_current_user_id` Does Not Check Token Blacklist**
`app/api/auth.py:186` — The auth dependency used by every protected endpoint calls the sync `decode_access_token()` which skips the blacklist. Only `/api/auth/me` uses the async version that checks it. **Logout is functionally broken for the entire app.**

**SEC-C2. Admin Bearer Token Authentication Allows Latent Privilege Escalation**
`app/api/auth.py:296-306` — `verify_admin` accepts JWT tokens with `role: "admin"` or `is_admin: true` claims, but no endpoint ever sets these claims. Dead code that widens the attack surface.

**SEC-C3. Admin Session Cookie Is Static (No Rotation)**
`app/api/admin_views.py:96-101` — The admin cookie is `HMAC(secret_key, "admin_username:admin")` — deterministic, no nonce, no timestamp. Once obtained, it works forever. All admin sessions share the same token.

### Database

**DB-C1. Schema Drift: `sources` and `global_settings` Tables Missing from `supabase_schema.sql`**
`scripts/supabase_schema.sql` — These tables exist in `database.py` init but not in the schema file. Fresh deploy = broken database.

**DB-C2. Schema Drift: `error_logs` Column Mismatch**
`supabase_schema.sql:43-47` — Schema has `context TEXT`; code uses `source`, `endpoint`, `additional_context JSONB`. Migration 011 fixes running DBs but schema file was never updated.

**DB-C3. Schema Drift: `stills` Table Column Names Diverged**
`supabase_schema.sql:86-87` — Schema says `times_used`/`last_used`; code uses `usage_count`/`last_used_at`. Fresh deploy = drafting service crashes.

**DB-C4. Schema Drift: `brand_voice_config.company_info` Missing**
`supabase_schema.sql:376-391` — Column exists in `database.py` init but not schema file. Fresh deploy = brand voice errors.

### Pipeline & Services

**PIPE-C1. Pipeline Over-Engineering: 18+ Sequential AI Calls Per Job**
`app/services/pipeline_steps.py` — A single job with 3 LinkedIn posts + 1 blog makes ~18 AI API calls in sequence: transcription, source of truth, summarization, distillation pass 1, distillation pass 2, drafting (per asset), editing (per draft), fact-checking (per draft), scoring (per draft), hook generation, image prompts. Editing + fact-checking + scoring could be one "Review" call. Distillation pass 2 is marginal.

**PIPE-C2. Cost Tracking Is Completely Broken**
`app/services/ai_client.py:301-303` — `calculate_openrouter_cost()` always returns 0.0 (hardcoded). `update_job_status()` accepts `cost_to_add` but never writes it to the database. Cost tracking is a no-op everywhere.

**PIPE-C3. Streaming Path Blocks the Event Loop**
`app/services/ai_client.py:128-137` — The streaming iterator is synchronous (`for chunk in stream:`) which blocks the asyncio event loop between chunks while waiting for network I/O.

**PIPE-C4. ~600+ Lines of Dead SQLite Code Paths**
Every service file — `if not settings.use_postgres:` branches that can never execute since `use_postgres` always returns `True`. 30+ locations across 12+ files.

### Backend API

**API-C1. Token Blacklist Bypass** (same as SEC-C1, confirmed by second auditor)

**API-C2. Admin Templates Call API Without Auth Headers**
`app/templates/admin/library_browser.html:126,155,233` — Admin templates call `/api/library/stats`, `/api/library`, etc. without Bearer tokens. These endpoints require auth → always 401. **Admin library browser and error log viewer are broken.**

**API-C3. Wrong API URL in Admin Client Detail View**
`app/templates/admin/client_view.html:96` — Calls `/admin/clients/${clientId}` (HTML router) instead of `/api/admin/clients/${clientId}` (API router). Returns 404.

### Frontend

**FE-C1. ES6 Module Race Condition Breaks results.html and settings.html**
`results.html:559`, `settings.html:649` — These pages load auth via ES6 modules (deferred) but call `Auth.requireAuth()` in regular inline `<script>` blocks that execute before modules load. `Auth` is `undefined` → JavaScript crash → **pages don't work**.

**FE-C2. Auth Tokens Stored in localStorage (XSS Target)**
`login.html:201`, `static/auth.js:9` — JWT tokens in localStorage are accessible to any JS on the page. Combined with user-generated content rendering, this is a token theft vector.

**FE-C3. No Token Refresh Mechanism**
All frontend files — Zero token refresh logic. When 7-day tokens expire, users get silently logged out on next API call. No proactive check, no warning.

### Config & Deployment

**CFG-C1. `aiosqlite` Still Imported Despite PostgreSQL-Only Declaration**
`requirements.txt:8`, `database.py:8` — Dead dependency, dead import, 600+ lines of dead code.

**CFG-C2. Backup Script Is Completely Broken**
`scripts/backup_db.py` — Entire script uses `sqlite3` stdlib. There is **no PostgreSQL backup mechanism**. If data loss occurs, no application-level backup exists.

**CFG-C3. Global Exception Handler Has Column Mismatch**
`app/main.py:69` — Inserts `(error_type, error_message, stack_trace, context)` but the `error_logs` table has no `context` column (it has `additional_context`). Insert silently fails → **no unhandled errors are persisted**.

### Testing

**TEST-C1. conftest.py Is Fundamentally Broken**
`tests/conftest.py:13-18` — Sets a SQLite `DATABASE_PATH` but `use_postgres=True` means the PostgreSQL branch is always taken. The `test_db` fixture creates/deletes a SQLite file nothing ever uses.

**TEST-C2. test_database.py Uses Raw SQLite API**
`tests/test_database.py:12-15` — `SELECT name FROM sqlite_master`, `?` placeholders, `cursor.fetchall()`, `db.commit()` — all SQLite-specific. Every test crashes against PostgreSQL.

**TEST-C3. test_lifecycle.py Uses SQLite SQL Syntax**
`tests/test_lifecycle.py:17-19` — Uses `?` placeholders and `datetime('now')`. All 6 tests are broken.

**TEST-C4. test_error_logger.py Depends on Broken Fixture**
`tests/test_error_logger.py:18-19` — Depends on `test_db` which is broken (TEST-C1).

**TEST-C5. E2E Tests Have Shared Mutable State**
`tests/test_e2e.py:21-30` — `TestConfig` class with mutable class-level state. Tests depend on sequential execution but pytest doesn't guarantee order without `pytest-ordering` (not installed).

**TEST-C6. E2E Tests Hit Real AI APIs With No Mocking**
`tests/test_e2e.py:15` — Tests hit a real running server that calls OpenRouter, Gemini, Claude APIs. Real costs, flaky, slow, can't run in CI.

---

## HIGH FINDINGS (38)

### Security (7)

| ID | Finding | File |
|----|---------|------|
| SEC-H1 | SSRF via autopilot feed URLs — no private IP blocking | `services/autopilot.py:27-43` |
| SEC-H2 | 7-day JWT expiry with no refresh token mechanism | `services/auth.py:21` |
| SEC-H3 | Registration rate limit is 500/hour (meant for E2E testing) | `api/auth.py:26` |
| SEC-H4 | Rate limiter uses `hash(token) % 1000000` — collisions likely | `rate_limiter.py:14` |
| SEC-H5 | `mark_output_performer` lacks user authorization check (IDOR) | `api/refresh.py:204-240` |
| SEC-H6 | Debug mode leaks full exception messages to client | `main.py:91` |
| SEC-H7 | Admin API key save only stores in `os.environ` — lost on restart | `api/admin.py:599-617` |

### Database (5)

| ID | Finding | File |
|----|---------|------|
| DB-H1 | Hardcoded `= TRUE` in SQL queries (7 locations) — violates coding standard | `webhook_manager.py:54`, `autopilot.py:120`, `memory.py:57`, etc. |
| DB-H2 | `CURRENT_TIMESTAMP` inconsistency across queries | `feedback.py:72`, `calendar.py:380`, `admin.py:199` |
| DB-H3 | Raw SQL bypassing `db_utils` in 12+ service files | `auth.py:91`, `drafting.py:47`, `brand_voice.py:203`, etc. |
| DB-H4 | Multi-write operations without transactions (6 locations) | `edit.py:208-227`, `library.py:490-535`, `autopilot.py:229`, etc. |
| DB-H5 | `json.loads()` on JSONB columns — fragile if asyncpg codec registered | Multiple API files |

### Pipeline & Services (6)

| ID | Finding | File |
|----|---------|------|
| PIPE-H1 | Source of Truth data generated but never passed to distillation | `pipeline_steps.py:168-181` |
| PIPE-H2 | Three separate "editor" services with overlapping responsibilities | `editing.py`, `content_editor.py`, `ai_editor.py` |
| PIPE-H3 | `still_matcher.py` is orphaned — never called from any route | `services/still_matcher.py` |
| PIPE-H4 | `data/settings.json` is never read by the application | `data/settings.json` |
| PIPE-H5 | Retry logic only covers non-streaming path | `ai_client.py:104-149` |
| PIPE-H6 | Circuit breakers defined but never used | `utils/retry.py:246-247` |

### Backend API (5)

| ID | Finding | File |
|----|---------|------|
| API-H1 | `edit/tone-presets` endpoint has no authentication | `api/edit.py:43-48` |
| API-H2 | `content_library` missing lifecycle columns in PG schema init | `database.py:364-381` |
| API-H3 | Dynamic SQL `IN` clauses have inconsistent PG/SQLite paths | `jobs.py:203-207`, `library.py:464`, `batch.py:203` |
| API-H4 | `refresh.py` bulk retire targets wrong table (`stills` vs `content_library`) | `api/refresh.py:96-101` |
| API-H5 | `error_logs` schema mismatch — global errors never persisted | `main.py:67-77` |

### Frontend (4)

| ID | Finding | File |
|----|---------|------|
| FE-H1 | Duplicate JS files with diverging implementations (auth.js x2, utils.js x2) | `static/auth.js` vs `static/js/auth.js` |
| FE-H2 | results.html missing `copyWithFeedback` from ES6 utils | `results.html:1406,1555` |
| FE-H3 | Hardcoded dark colors in agent terminal break light theme | `results.html:121-201` |
| FE-H4 | `library.html` still exists as orphaned stale file | `frontend/library.html` |

### Config & Deployment (6)

| ID | Finding | File |
|----|---------|------|
| CFG-H1 | SSL cert verification disabled for DB connections | `database.py:62-63` |
| CFG-H2 | Health check doesn't verify database connectivity | `main.py:335-338` |
| CFG-H3 | Single uvicorn worker in production (no `--workers`) | `Procfile`, `railway.toml`, `nixpacks.toml` |
| CFG-H4 | Admin credentials default to empty strings — no prod enforcement | `config.py:47-48` |
| CFG-H5 | `database_url` defaults to empty string — no prod validation | `config.py:23` |
| CFG-H6 | No logging configuration — all `logger.info()` calls are invisible | `main.py` |

### Testing (5)

| ID | Finding | File |
|----|---------|------|
| TEST-H1 | Zero mocking in entire test suite | All test files |
| TEST-H2 | ~140 API routes, only ~10 have any unit test coverage (~7%) | All API modules |
| TEST-H3 | ~25 services with zero test coverage | All service modules |
| TEST-H4 | E2E Playwright tests require live server with real database | `playwright.config.ts:26-33` |
| TEST-H5 | E2E tests create data but never clean up | `e2e/auth.spec.ts`, `e2e/api.spec.ts` |

---

## MEDIUM FINDINGS (56)

### Security (9)
- No password special character requirement
- Admin login `next` parameter open redirect fragment
- CORS `allow_headers=["*"]` with credentials
- File upload validates extension only, not content/magic bytes
- Webhook delivery URLs not validated for private IPs
- No account lockout after failed logins
- `edit/tone-presets` unauthenticated (inconsistent security model)
- `bulk_retire` updates wrong table
- Error endpoint accepts optional auth (abuse vector)

### Database (8)
- `aiosqlite` still imported and in requirements
- Dynamic `IN` clauses inconsistent with db_utils
- N+1 query pattern in swipe tag filtering
- `date()` function prevents index usage in admin queries
- Race condition in feedback upsert (SELECT then INSERT/UPDATE)
- Race condition in brand voice config upsert
- Missing single-column index for `outputs.job_id`
- `stills_used LIKE ?` for JSON search (full table scan)

### Pipeline & Services (8)
- Duplicate `DEFAULT_PERSONA` definitions in drafting.py and editing.py
- Pipeline steps never return `success=False` (field is useless)
- Prompt templates can crash on missing variables (`str.format()` + `KeyError`)
- `process_job_from_library` duplicates pipeline logic (misses scoring, hooks, image prompts)
- `settings_manager.py` atomization/distillation aliasing confusion
- Sommelier makes TWO AI calls per search (one just to parse keywords)
- Inconsistent cost tracking — some services try, others don't, all return $0
- Sequential processing where `asyncio.gather()` could parallelize

### Backend API (7)
- Admin settings endpoint silently swallows errors
- Swipe tag filter applied client-side after SQL fetch (broken pagination)
- Inconsistent error handling for DELETE operations
- `datetime.utcnow()` deprecated (used throughout)
- Admin error logs endpoint creates tables at runtime (DDL in endpoint handler)
- Memory rule `is_active = TRUE` violates coding standard
- Route ordering concerns in swipes.py

### Frontend (8)
- Inconsistent script loading (legacy vs ES6 modules across pages)
- Font Awesome loaded on only 2 pages
- Missing `novalidate` consistency on forms
- Export function in results.html bypasses auth wrapper
- `refresh.js` defines duplicate `getToken()` and `formatDate()`
- No CSRF protection (acceptable with Bearer tokens, but noted)
- Missing `aria-label` on navbar logo
- **Tailwind CDN in production** (all 18 HTML files load dev-only CDN)

### Config & Deployment (9)
- `.env.example` UPLOAD_MAX_SIZE_MB (500) differs from config.py default (100)
- CORS `allow_headers=["*"]` overly permissive
- Outdated package versions (jinja2 CVE-2024-22195, passlib unmaintained)
- `bcrypt` redundantly listed alongside `passlib[bcrypt]`
- `package.json` has no scripts (no way to run Playwright tests)
- `datetime.utcnow()` deprecated
- `.env.example` still references SQLite as fallback
- Rate limiter hash collision risk
- nixpacks.toml pins Python 3.11

### Testing (7)
- Tests that can never fail (`assert True`, conditional test bodies)
- Admin tests accept 3 status codes including 503
- `test_upload_requires_persona` tests the wrong thing (asserts 200 for invalid input)
- No test isolation between database tests
- E2E authenticated page tests are fragile
- Playwright `beforeAll` token may not propagate in parallel mode
- No edge case testing for critical paths (uploads, auth, pagination, race conditions)

---

## LOW FINDINGS (50)

*(Grouped by category — details in individual audit reports)*

**Security (7):** Weak default admin credentials in .env.example, secret key auto-generation without persistence, deprecated datetime.utcnow(), missing rate limits on LLM-calling endpoints, admin logout via GET (CSRF), implicit CSRF reliance, error endpoint abuse potential.

**Database (6):** Dead `get_db_connection()` function, deprecated datetime.utcnow(), dead `if not use_postgres: commit()` branches, `SELECT *` usage, pagination without upper bound on `limit`, dead `context` column in schema.

**Pipeline (7):** `data/settings.json` contains stale "atomization" key, default personas hardcoded in two places, fragile string matching on step names, cost reset bookkeeping accomplishes nothing, three error logging implementations, prompt manager stores unused model/max_tokens, scoring reuses FACTCHECKING status.

**Backend API (9):** Unused imports (6 files), duplicate `_row_to_persona_dict` function, `PersonaCreate` missing `language_level`, auth models lack EmailStr validation, `WebhookCreate` no URL length limit, admin prompt update uses query params for body data, `BatchStatusResponse.created_at` typed wrong, `generate_from_library` bypasses fetchall helper, error_logs schema column name mismatch.

**Frontend (8):** Dead `index.js` module, `request-cache.js` underused, **no mobile navigation**, duplicate Tailwind config across 18 files, `no-transitions` pattern, inconsistent font family declarations, stale `copy-toast` element, brand-voice CSS load order.

**Config (8):** `.gitignore` missing env patterns, `pytest.ini` suppresses all DeprecationWarnings, frontend routes hardcoded (fragile), port mismatch (5000/8000/5001), start command in 3 places, exact version pinning everywhere, openai package not optional despite comment, 5-minute health check timeout.

**Testing (5):** Manual test checklist references "Replit", conftest `event_loop` may conflict with pytest-asyncio, test_e2e.py shadows conftest fixtures, `sample_stills` fixture far from usage, `test_still_matcher.py` only tests one scenario.

---

## Recommended Priority Actions

### Tier 1: Fix What's Broken Right Now
1. **Fix `get_current_user_id` to check token blacklist** (SEC-C1) — single most impactful security fix
2. **Fix ES6 module race condition** on results.html and settings.html (FE-C1)
3. **Fix `error_logs` column mismatch** in main.py so errors actually get logged (CFG-C3/API-H5)
4. **Fix admin template API calls** — add auth headers, fix wrong URL prefix (API-C2/API-C3)
5. **Regenerate `supabase_schema.sql`** from the actual `database.py` init (DB-C1 through DB-C4)

### Tier 2: Simplify the Architecture
6. **Collapse the content pipeline** — merge editing + fact-checking + scoring into one "Review" call; make distillation pass 2 optional; remove sommelier's query-parsing AI call (~60% reduction in AI calls per job)
7. **Remove all SQLite dead code** — delete every `if not use_postgres:` branch, remove `aiosqlite` from requirements, delete the broken backup script (PIPE-C4/CFG-C1/CFG-C2)
8. **Consolidate the three editor services** into one (PIPE-H2)
9. **Consolidate duplicate JS files** — pick ES6 modules or legacy, not both (FE-H1)
10. **Remove dead code** — `still_matcher.py`, circuit breakers, `data/settings.json`, `library.html`, `get_db_connection()` (PIPE-H3/H4/H6, FE-H4, DB-L1)

### Tier 3: Shore Up Security
11. **Add SSRF protection** — block private IPs in autopilot and webhook URL fetching (SEC-H1)
12. **Fix admin session management** — per-session nonces, expiration (SEC-C3)
13. **Fix IDOR in `mark_output_performer`** — add user_id check (SEC-H5)
14. **Lower registration rate limit** from 500/hour to ~10/hour (SEC-H3)
15. **Implement token refresh** — reduce JWT expiry from 7 days, add refresh token flow (SEC-H2)
16. **Enable SSL verification** for database connections (CFG-H1)

### Tier 4: Fix Infrastructure
17. **Add uvicorn workers** for production (CFG-H3)
18. **Configure logging** so `logger.info()` calls actually work (CFG-H6)
19. **Add database connectivity to health check** (CFG-H2)
20. **Fix cost tracking** or remove it — currently 100% broken (PIPE-C2)
21. **Add transaction wrapping** to multi-write operations (DB-H4)
22. **Write a PostgreSQL backup script** (CFG-C2)

### Tier 5: Fix Testing
23. **Rewrite conftest.py** for PostgreSQL (Docker container or test schema) (TEST-C1)
24. **Add mocking layer** for AI client (TEST-H1)
25. **Rewrite SQLite-based tests** to use db_utils (TEST-C2/C3)
26. **Add tests for auth service** — security-critical with zero coverage (TEST-H3)

### Tier 6: Frontend Polish
27. **Add mobile navigation** (FE-L3 — listed as Low but it's really a product gap)
28. **Switch from Tailwind CDN to build step** (FE-M8)
29. **Extract shared Tailwind config** instead of copying across 18 files (FE-L4)
30. **Fix Source of Truth data flow** so it actually reaches distillation (PIPE-H1)
