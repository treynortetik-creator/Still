# ContentMultiplier - Project Context for Claude

## Project Overview
AI-powered content repurposing platform (FastAPI + vanilla JS frontend) deployed on Railway.

## Current Priority: Supabase PostgreSQL Migration

### Migration Status: NOT STARTED
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

### Phase 1: Core Infrastructure [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/config.py` - Add DATABASE_URL config
- [ ] `app/database.py` - Replace aiosqlite with asyncpg pool
- [ ] `requirements.txt` - Add `asyncpg`
- [ ] Create PostgreSQL schema in Supabase dashboard

**Tables:** users, revoked_tokens

**Test:** User registration, login, logout

---

### Phase 2: Authentication & Users [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/auth.py`
- [ ] `app/services/auth.py`

**Test:** Full auth flow - register, login, token refresh, logout

---

### Phase 3: Core Content Pipeline [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/upload.py`
- [ ] `app/api/jobs.py`
- [ ] `app/services/pipeline.py`
- [ ] `app/services/sommelier.py`

**Tables:** jobs, stills, outputs

**Test:** Upload content → Quick Distill → Generate from stills

---

### Phase 4: Content Management [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/library.py`
- [ ] `app/api/workshop.py`
- [ ] `app/api/edit.py`
- [ ] `app/api/export.py`
- [ ] `app/services/library_manager.py`

**Tables:** content_library, output_edits, output_feedback

**Test:** Library browse, workshop editing, export

---

### Phase 5: Personas & Brand Voice [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/personas.py`
- [ ] `app/api/custom_personas.py`
- [ ] `app/api/brand_voice.py`
- [ ] `app/services/persona_manager.py`
- [ ] `app/services/brand_voice_analyzer.py`

**Tables:** personas, brand_voice_profiles, brand_voice_samples, brand_voice_config

**Test:** Create persona, analyze brand voice, generate with persona

---

### Phase 6: Advanced Features [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/batch.py`
- [ ] `app/api/calendar.py`
- [ ] `app/api/autopilot.py`
- [ ] `app/services/batch_processor.py`
- [ ] `app/services/autopilot.py`

**Tables:** batches, content_schedule, autopilot_sources, autopilot_items

**Test:** Batch upload, calendar scheduling, autopilot monitors

---

### Phase 7: Integrations & Analytics [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/webhooks.py`
- [ ] `app/api/analytics.py`
- [ ] `app/api/swipes.py`
- [ ] `app/api/memory.py`
- [ ] `app/api/feedback.py`
- [ ] `app/services/webhook_manager.py`
- [ ] `app/services/swipe_analyzer.py`

**Tables:** webhooks, webhook_deliveries, swipe_files, swipe_analysis, memory_rules, error_logs, rate_limits

**Test:** Webhook delivery, analytics display, swipe file analysis

---

### Phase 8: Admin & Utilities [ ]
**Status:** NOT STARTED
**Files:**
- [ ] `app/api/admin.py`
- [ ] `app/services/prompt_manager.py`
- [ ] `app/services/ai_editor.py`
- [ ] `app/services/image_prompts.py`
- [ ] `app/services/remix.py`

**Tables:** prompt_templates, ai_model_config, ai_editor_config, image_prompts

**Test:** Admin panel, prompt management, AI model config

---

## Completed Migrations
_(Move phases here when done)_

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

## Other Project Notes
- Deployed on Railway with nixpacks
- Frontend: vanilla JS + Tailwind in `/frontend`
- Uses Gemini and Claude APIs for AI processing
