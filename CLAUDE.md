# ContentMultiplier - Project Context for Claude

## Project Overview
AI-powered content repurposing platform (FastAPI + vanilla JS frontend) deployed on Railway.

## Current Priority: Supabase PostgreSQL Migration

### Migration Status: ALL PHASES COMPLETE
**Approach:** Hybrid Option A - Migrate 2-5 related features per phase, test, deploy, repeat.

### Connection Details (DO NOT COMMIT ACTUAL CREDENTIALS)
- Use Transaction Mode: port `6543` (NOT 5432)
- Connection string format: `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:6543/postgres`
- Requires: `statement_cache_size=0` (for PgBouncer)
- Store in environment variable: `DATABASE_URL`

### SQL Syntax Changes Reference
| SQLite | PostgreSQL |
|--------|------------|
| `?` placeholders | `$1, $2, $3` |
| `datetime('now')` | `NOW()` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `REAL` | `FLOAT` or `DOUBLE PRECISION` |
| `json` columns | `JSONB` |
| `PRAGMA foreign_keys = ON` | (enabled by default) |
| `executescript()` | Multiple `execute()` calls |

---

## Migration Phases

### Phase 1: Core Infrastructure [x]
**Status:** COMPLETE
**Files:**
- [x] `app/config.py` - Add DATABASE_URL config
- [x] `app/database.py` - Replace aiosqlite with asyncpg pool
- [x] `requirements.txt` - Add `asyncpg`
- [x] Create PostgreSQL schema in Supabase dashboard
- [x] `app/db_utils.py` - Created compatibility helpers for SQLite/PostgreSQL

**Tables:** users, revoked_tokens

**Test:** User registration, login, logout

---

### Phase 2: Authentication & Users [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/auth.py`
- [x] `app/services/auth.py`

**Test:** Full auth flow - register, login, token refresh, logout

---

### Phase 3: Core Content Pipeline [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/upload.py`
- [x] `app/api/jobs.py`
- [x] `app/services/pipeline.py`
- [x] `app/services/sommelier.py`

**Tables:** jobs, stills, outputs

**Test:** Upload content → Quick Distill → Generate from stills

---

### Phase 4: Content Management [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/library.py`
- [x] `app/api/workshop.py`
- [x] `app/api/edit.py`
- [x] `app/api/export.py`
- [x] `app/services/library_manager.py`

**Tables:** content_library, output_edits, output_feedback

**Test:** Library browse, workshop editing, export

---

### Phase 5: Personas & Brand Voice [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/personas.py`
- [x] `app/api/custom_personas.py`
- [x] `app/api/brand_voice.py`
- [x] `app/services/persona_manager.py`
- [x] `app/services/brand_voice_analyzer.py`

**Tables:** personas, brand_voice_profiles, brand_voice_samples, brand_voice_config

**Test:** Create persona, analyze brand voice, generate with persona

---

### Phase 6: Advanced Features [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/batch.py`
- [x] `app/api/calendar.py`
- [x] `app/api/autopilot.py`
- [x] `app/services/batch_processor.py`
- [x] `app/services/autopilot.py`

**Tables:** batches, content_schedule, autopilot_sources, autopilot_items

**Test:** Batch upload, calendar scheduling, autopilot monitors

---

### Phase 7: Integrations & Analytics [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/webhooks.py`
- [x] `app/api/analytics.py`
- [x] `app/api/swipes.py`
- [x] `app/api/memory.py`
- [x] `app/api/feedback.py`
- [x] `app/services/webhook_manager.py`
- [x] `app/services/swipe_analyzer.py`

**Tables:** webhooks, webhook_deliveries, swipe_files, swipe_analysis, memory_rules, error_logs, rate_limits

**Test:** Webhook delivery, analytics display, swipe file analysis

---

### Phase 8: Admin & Utilities [x]
**Status:** COMPLETE
**Files:**
- [x] `app/api/admin.py`
- [x] `app/services/prompt_manager.py`
- [x] `app/services/ai_editor.py`
- [x] `app/services/image_prompts.py`
- [x] `app/services/remix.py`

**Tables:** prompt_templates, ai_model_config, ai_editor_config, image_prompts

**Test:** Admin panel, prompt management, AI model config

---

## Completed Migrations

All 8 phases have been migrated to support both SQLite and PostgreSQL.

---

## Notes & Decisions
- Using asyncpg directly (not Supabase Python SDK) for better FastAPI integration
- Keeping existing JWT auth system (not migrating to Supabase Auth)
- Local development can continue with SQLite if needed (optional dual-support)

---

## How to Update This File
When working on migration:
1. Mark current phase as "IN PROGRESS"
2. Check off files as they're completed: `[ ]` → `[x]`
3. Add any issues/notes discovered during migration
4. When phase complete, move to "Completed Migrations" section
5. Commit this file with migration changes

---

## Coding Standards

### Boolean Handling in SQL Queries
When querying boolean columns across SQLite and PostgreSQL:

**DO:** Use parameterized queries with Python booleans
```python
# Correct - works on both SQLite and PostgreSQL
rows = await fetchall(db, "SELECT * FROM table WHERE is_active = ?", (True,))
```

**DON'T:** Use hardcoded SQL boolean keywords
```python
# WRONG - TRUE keyword not recognized in SQLite
rows = await fetchall(db, "SELECT * FROM table WHERE is_active = TRUE")

# WRONG - Integer literals work but are less readable
rows = await fetchall(db, "SELECT * FROM table WHERE is_active = 1")
```

The `db_utils.py` helpers automatically convert `?` placeholders to `$1, $2...` for PostgreSQL, and Python's `True`/`False` are properly handled by both database drivers.

---

## Other Project Notes
- Deployed on Railway with nixpacks
- Frontend: vanilla JS + Tailwind in `/frontend`
- Uses Gemini and Claude APIs for AI processing
