# Claude Memory File - Still Project

## Project Overview
**Name:** ContentMultiplier (Still)
**Type:** AI-powered content repurposing platform
**Stack:** FastAPI + vanilla JS frontend
**Deployment:** Railway (backend) + Supabase (PostgreSQL)

## MCP Integrations

### Supabase MCP
- **Location:** Cursor MCP config at `~/.cursor/mcp.json`
- **Project Ref:** `your-project-ref`
- **URL:** `https://mcp.supabase.com/mcp?project_ref=your-project-ref`
- **Usage:** Database operations, schema management

### Other MCPs Available
- **context7:** `@upstash/context7-mcp` - Context management
- **playwright:** `@playwright/mcp@latest` - Browser automation/testing

## Database Configuration

### Connection Details
- **Mode:** Transaction Mode (port 6543, NOT 5432)
- **Format:** `postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:6543/postgres`
- **Required:** `statement_cache_size=0` (for PgBouncer)
- **Env Var:** `DATABASE_URL`

### Key Tables for Settings
| Table | Purpose | Status |
|-------|---------|--------|
| `ai_model_config` | AI model per pipeline step | EXISTS - needs full wiring |
| `ai_editor_config` | Workshop AI editor settings | EXISTS - fully wired |
| `global_settings` | OpenRouter toggle, global configs | NEEDS CREATION |
| `prompt_templates` | Prompt templates per step | EXISTS - fully wired |

## File vs Database Storage

### Currently File-Based (PROBLEM)
- `data/settings.json` - Model configs, OpenRouter toggle (LOST on redeploy)
- `data/personas.json` - Default personas (read-only fallback OK)
- `data/prompts/*.txt` - Loaded at startup into DB (OK)

### Database-Backed (GOOD)
- `ai_model_config` - Partially wired
- `ai_editor_config` - Fully wired
- `prompt_templates` - Fully wired
- `brand_voice_config` - Fully wired
- User data (personas, content, jobs, etc.)

## Key Architecture Files

| File | Purpose |
|------|---------|
| `app/database.py` | Schema definitions, connection pool |
| `app/db_utils.py` | SQLite/PostgreSQL abstraction |
| `app/config.py` | Environment config, paths |
| `app/services/settings_manager.py` | Model config (FILE-BASED - needs migration) |
| `app/services/ai_editor.py` | Editor config (DB-backed) |
| `app/api/admin.py` | Admin endpoints |

## SQL Syntax Differences

| SQLite | PostgreSQL |
|--------|------------|
| `?` placeholders | `$1, $2, $3` |
| `datetime('now')` | `NOW()` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `REAL` | `FLOAT` or `DOUBLE PRECISION` |
| `json` columns | `JSONB` |

## Common Commands

```bash
# Run tests
python -m pytest tests/test_api.py tests/test_database.py -x -q

# Start dev server
source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload

# Check imports
python -c "from app.main import app; print('OK')"
```

## Recent Changes Log

### 2024-12-30 (Latest)
- **Database-backed settings migration:**
  - Added `global_settings` table for use_openrouter and other config
  - Migrated `settings_manager.py` to read/write from database instead of files
  - Added in-memory cache with thread-safe access for synchronous calls
  - Settings now persist across Railway redeploys
  - Created PostgreSQL migration: `migrations/002_global_settings.sql`
- Added global JSON exception handler (errors now return JSON, not plain text)
- Fixed atomization/distillation alias in settings_manager
- All errors now logged to `error_logs` table
