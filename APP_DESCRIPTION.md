# Still - AI Content Repurposing Platform

## Application Overview

**Still** is a production-ready AI-powered content repurposing platform that transforms long-form content (videos, podcasts, PDFs, text) into multi-channel marketing campaigns. Built with FastAPI backend and vanilla JavaScript frontend, deployed on Railway with Supabase PostgreSQL.

**Primary Use Case:** Take a webinar, podcast, or document and automatically generate LinkedIn posts, blog articles, and email sequences tailored to specific audience personas.

---

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL via Supabase (with SQLite fallback for local dev)
- **Async Database:** asyncpg (PostgreSQL), aiosqlite (SQLite)
- **Authentication:** JWT tokens via python-jose, bcrypt password hashing
- **Validation:** Pydantic v2 with pydantic-settings
- **Rate Limiting:** slowapi

### Frontend
- **Framework:** Vanilla JavaScript (no build tools)
- **Styling:** Tailwind CSS (CDN)
- **State:** localStorage + cookies for JWT tokens

### AI/ML Services
- **Transcription:** Google Gemini 2.0 Flash
- **Content Distillation:** Gemini 2.0 Flash
- **Content Drafting:** Claude Opus 4.5 (via OpenRouter or direct Anthropic API)
- **Editing/Fact-checking:** Gemini 2.5 Flash

### Deployment
- **Hosting:** Railway.app
- **Database:** Supabase (Transaction Mode, port 6543)
- **Build:** Nixpacks
- **Storage:** Railway volume mount for persistent data

---

## Project Structure

```
Still/
├── app/                      # Python FastAPI backend
│   ├── main.py              # FastAPI app initialization, middleware, route registration
│   ├── config.py            # Pydantic settings, environment config
│   ├── database.py          # Database initialization (PostgreSQL + SQLite fallback)
│   ├── db_utils.py          # SQL compatibility helpers (PostgreSQL/SQLite abstraction)
│   ├── api/                 # 22 API router modules
│   │   ├── auth.py          # User registration, login, logout, token refresh
│   │   ├── upload.py        # File/text upload, quick distill mode
│   │   ├── jobs.py          # Job status, results, listing
│   │   ├── library.py       # Content library ("The Reserve") management
│   │   ├── workshop.py      # Output editing workspace
│   │   ├── edit.py          # AI-assisted editing endpoints
│   │   ├── export.py        # Export to CSV, JSON, copy to clipboard
│   │   ├── personas.py      # System persona management
│   │   ├── custom_personas.py # User-created personas
│   │   ├── brand_voice.py   # Brand voice analysis and config
│   │   ├── batch.py         # Batch file processing (2-10 files)
│   │   ├── calendar.py      # Content scheduling
│   │   ├── autopilot.py     # RSS/webhook source monitoring
│   │   ├── webhooks.py      # Zapier/external webhook integration
│   │   ├── swipes.py        # Swipe file collection and "Style DNA"
│   │   ├── memory.py        # Persistent brand rules/guidelines
│   │   ├── remix.py         # Re-generate with different persona/tone
│   │   ├── sommelier.py     # Content rating and review
│   │   ├── feedback.py      # User feedback collection
│   │   ├── analytics.py     # Usage stats, cost tracking, ROI
│   │   ├── admin.py         # Admin API (prompts, models, settings)
│   │   └── admin_views.py   # Admin HTML dashboard
│   ├── services/            # 27 business logic modules
│   │   ├── pipeline.py      # Main orchestrator (1183 lines) - coordinates all steps
│   │   ├── transcription.py # Video/audio → text, PDF extraction
│   │   ├── distillation.py  # Extract "stills" (quotes, stats, stories, etc.)
│   │   ├── drafting.py      # Generate LinkedIn/blog/email using Claude
│   │   ├── editing.py       # Optimize for target audience
│   │   ├── factcheck.py     # Verify content accuracy
│   │   ├── scoring.py       # Rate quality (Hook, Brand, Clarity, Engagement)
│   │   ├── ai_client.py     # Unified OpenRouter/Anthropic/Gemini client
│   │   ├── prompt_manager.py # Load and render prompt templates
│   │   ├── persona_manager.py # Persona loading and application
│   │   ├── brand_voice_analyzer.py # Analyze and apply brand voice
│   │   ├── library_manager.py # Content library operations
│   │   ├── batch_processor.py # Concurrent batch processing
│   │   ├── autopilot.py     # Monitor RSS feeds for new content
│   │   ├── scheduler.py     # Background job scheduler
│   │   ├── webhook_manager.py # Webhook delivery with retries
│   │   ├── swipe_analyzer.py # Extract "Style DNA" from examples
│   │   ├── remix.py         # Content remix logic
│   │   ├── hook_generator.py # Generate attention hooks
│   │   ├── ai_editor.py     # AI editing suggestions
│   │   ├── image_prompts.py # Generate image prompts for posts
│   │   ├── content_editor.py # Content refinement
│   │   ├── settings_manager.py # User settings management
│   │   └── auth.py          # JWT, password hashing, token blacklist
│   ├── models/              # Pydantic data models
│   │   ├── job.py           # Job, JobStatus enums
│   │   ├── output.py        # Output content with quality scores
│   │   ├── stills.py        # Extracted content "stills"
│   │   ├── persona.py       # Persona definitions
│   │   ├── library_entry.py # Content library entries
│   │   ├── batch.py         # Batch processing
│   │   ├── calendar.py      # Scheduled content
│   │   ├── webhook.py       # Webhook configuration
│   │   ├── autopilot.py     # Autopilot sources and items
│   │   ├── workshop.py      # Workshop editing state
│   │   ├── analytics.py     # Analytics models
│   │   └── brand_context.py # Brand voice context
│   ├── utils/               # Helper utilities
│   │   ├── validation.py    # Input validation (file size, text length)
│   │   ├── security.py      # Filename sanitization, path traversal prevention
│   │   ├── json_parser.py   # Robust JSON parsing from LLM responses
│   │   ├── retry.py         # Async retry with exponential backoff
│   │   ├── error_messages.py # Enhanced error handling
│   │   └── background_tasks.py # Background task management
│   └── templates/           # Admin Jinja2 templates
├── frontend/                # Static HTML + vanilla JS
│   ├── index.html           # Landing page
│   ├── login.html, register.html
│   ├── upload.html          # File upload interface
│   ├── status.html          # Job progress tracking
│   ├── results.html         # View generated content
│   ├── reserve.html         # Content library browser
│   ├── workshop.html        # Edit outputs with AI help
│   ├── settings.html        # User settings, brand voice testing
│   ├── calendar.html        # Content scheduling
│   ├── autopilot.html       # RSS/webhook monitors
│   ├── batch-status.html    # Batch processing status
│   ├── swipes.html          # Swipe file management
│   ├── analytics.html       # Usage analytics
│   ├── remix.html           # Content remix
│   ├── brand-voice.html     # Brand voice configuration
│   └── static/
│       ├── auth.js          # JWT token management
│       ├── utils.js         # API calls, formatting helpers
│       ├── components.js    # Reusable UI components
│       ├── theme.js         # Dark/light mode toggle
│       └── styles.css       # Tailwind + custom CSS
├── data/
│   ├── prompts/             # LLM prompt templates (8 files)
│   │   ├── distillation.txt
│   │   ├── distillation_pass2.txt # Multi-pass deep extraction
│   │   ├── linkedin_draft.txt
│   │   ├── blog_draft.txt
│   │   ├── email_draft.txt
│   │   ├── audience_edit.txt
│   │   ├── factcheck.txt
│   │   └── atomization.txt
│   ├── personas.json        # Default personas
│   └── settings.json        # Default settings
├── migrations/              # PostgreSQL migration scripts
├── scripts/
│   ├── supabase_schema.sql  # Full database schema
│   └── backup_db.py
├── tests/
│   ├── test_e2e.py          # End-to-end integration tests
│   ├── test_api.py
│   ├── test_services.py
│   └── test_database.py
├── requirements.txt         # Python dependencies
├── nixpacks.toml           # Railway build config
├── railway.toml            # Railway deployment config
└── CLAUDE.md               # Project context for AI assistants
```

---

## Database Schema

### Core Tables

```sql
-- Users and Authentication
users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    subscription_tier TEXT DEFAULT 'free',
    credits_remaining INTEGER DEFAULT 0,
    total_cost_incurred FLOAT DEFAULT 0.0,
    byok_enabled BOOLEAN DEFAULT FALSE,
    api_keys JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
)

revoked_tokens (
    token_hash TEXT PRIMARY KEY,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP DEFAULT NOW()
)

-- Processing Jobs
jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL,  -- uploading, transcribing, distilling, drafting, editing, complete, failed
    original_filename TEXT,
    file_type TEXT,  -- video, audio, pdf, text, image
    file_size INTEGER,
    target_persona TEXT,
    asset_types JSONB,  -- ["linkedin", "blog", "email"]
    asset_quantities JSONB,  -- {"linkedin": 3, "blog": 1}
    processing_mode TEXT DEFAULT 'autopilot',  -- autopilot, quick_distill
    original_transcript TEXT,
    cleaned_transcript TEXT,
    progress INTEGER DEFAULT 0,
    current_step TEXT,
    cost_incurred FLOAT DEFAULT 0.0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
)

-- Extracted Content "Stills"
stills (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    still_type TEXT NOT NULL,  -- insight, statistic, quote, story, actionable_advice, etc.
    content TEXT NOT NULL,
    source_location TEXT,  -- timestamp or page reference
    source_file TEXT,
    tags JSONB,
    persona_relevance JSONB,  -- which personas this is good for
    quote_attribution TEXT,
    times_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Generated Outputs
outputs (
    id SERIAL PRIMARY KEY,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL,  -- linkedin, blog, email
    variation_number INTEGER,
    step1_draft TEXT,      -- Initial draft from Claude
    step2_edited TEXT,     -- After audience optimization
    step3_final TEXT,      -- Final version
    atoms_used JSONB,      -- Which stills were used
    citations JSONB,       -- Source references
    warnings JSONB,        -- Fact-check warnings
    hooks JSONB,           -- Generated attention hooks
    quality_scores JSONB,  -- {"hook": 8, "brand": 7, "clarity": 9, "engagement": 8}
    image_prompt TEXT,
    user_edited_content TEXT,
    is_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Content Library ("The Reserve")
content_library (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    entry_type TEXT NOT NULL,  -- Same as still_type
    content TEXT NOT NULL,
    source TEXT,
    source_timestamp TEXT,
    speaker TEXT,
    date_added TIMESTAMP DEFAULT NOW(),
    tags JSONB,
    persona_relevance JSONB,
    times_used INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    campaign_name TEXT,
    topics JSONB,
    notes TEXT
)
```

### Feature Tables

```sql
-- Personas
personas (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    industry TEXT,
    pain_points JSONB NOT NULL,
    goals JSONB NOT NULL,
    tone_preferences JSONB,
    content_preferences JSONB,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Brand Voice
brand_voice_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    profile_name TEXT DEFAULT 'Primary Voice',
    vocabulary_patterns JSONB,
    sentence_structure JSONB,
    tone_markers JSONB,
    phrases_to_use JSONB,
    phrases_to_avoid JSONB,
    overall_summary TEXT,
    sample_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)

brand_voice_samples (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    profile_id INTEGER REFERENCES brand_voice_profiles(id),
    content TEXT NOT NULL,
    content_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Memory Rules (Persistent Brand Guidelines)
memory_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    rule_type TEXT NOT NULL,  -- avoid, prefer, format, tone
    rule_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Swipe Files (Style DNA)
swipe_files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    content TEXT NOT NULL,
    source_url TEXT,
    source_type TEXT DEFAULT 'general',
    title TEXT,
    tags JSONB,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)

swipe_analysis (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    analysis_type TEXT NOT NULL,
    patterns JSONB NOT NULL,  -- Extracted style patterns
    summary TEXT,
    swipe_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)

-- Batch Processing
batches (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    job_ids JSONB NOT NULL,
    total_jobs INTEGER NOT NULL,
    completed_jobs INTEGER DEFAULT 0,
    failed_jobs INTEGER DEFAULT 0,
    settings JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
)

-- Content Calendar
content_schedule (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    output_id INTEGER REFERENCES outputs(id) ON DELETE CASCADE,
    scheduled_date DATE NOT NULL,
    scheduled_time TIME DEFAULT '09:00:00',
    platform TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled',  -- scheduled, published, cancelled
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Autopilot (RSS/Webhook Monitoring)
autopilot_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    source_type TEXT NOT NULL,  -- rss, webhook
    source_url TEXT NOT NULL,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    check_interval_minutes INTEGER DEFAULT 60,
    last_checked TIMESTAMP,
    settings JSONB,
    created_at TIMESTAMP DEFAULT NOW()
)

autopilot_items (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES autopilot_sources(id),
    user_id INTEGER REFERENCES users(id),
    external_id TEXT,  -- GUID or unique ID from source
    title TEXT,
    content TEXT,
    url TEXT,
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, ignored
    job_id TEXT REFERENCES jobs(id),
    discovered_at TIMESTAMP DEFAULT NOW()
)

-- Webhooks (Zapier Integration)
webhooks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    trigger_events JSONB NOT NULL,  -- ["job.complete", "output.created"]
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, url)
)

webhook_deliveries (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER REFERENCES webhooks(id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Feedback and Editing
output_feedback (
    id SERIAL PRIMARY KEY,
    output_id INTEGER REFERENCES outputs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    feedback TEXT NOT NULL CHECK(feedback IN ('thumbs_up', 'thumbs_down')),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(output_id, user_id)
)

output_edits (
    id SERIAL PRIMARY KEY,
    output_id INTEGER REFERENCES outputs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    previous_content TEXT,
    new_content TEXT NOT NULL,
    edit_note TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)

-- Admin/System Tables
prompt_templates (
    id SERIAL PRIMARY KEY,
    template_name TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    max_tokens INTEGER DEFAULT 4000,
    prompt_content TEXT NOT NULL,
    variables JSONB,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)

ai_model_config (
    id SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,  -- transcription, distillation, drafting, editing, factcheck, scoring
    model_id TEXT NOT NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    cost_per_1k_input FLOAT DEFAULT 0.0,
    cost_per_1k_output FLOAT DEFAULT 0.0,
    max_tokens INTEGER DEFAULT 4096,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)

global_settings (
    id SERIAL PRIMARY KEY,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    setting_type TEXT DEFAULT 'string',
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)

error_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    job_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    stack_trace TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT NOW()
)

rate_limits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action_type TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
)
```

---

## Core Processing Pipeline

The main content processing flow (in `app/services/pipeline.py`):

### Step 1: Transcription
- **Input:** Video (MP4, MOV, WebM), Audio (MP3, WAV, M4A), PDF, Text, Image
- **Process:** Gemini 2.0 Flash extracts/transcribes content
- **Output:** Raw transcript text

### Step 2: Distillation (Extract "Stills")
- **Input:** Transcript text
- **Process:** AI extracts reusable content elements:
  - **Insights** - Key takeaways, observations
  - **Statistics** - Data points, percentages, metrics
  - **Quotes** - Memorable statements with attribution
  - **Stories** - Anecdotes, case studies, examples
  - **Actionable Advice** - How-to steps, recommendations
  - **Contrarian Takes** - Unconventional perspectives
  - **Frameworks** - Mental models, processes
- **Multi-pass option:** `distillation_pass2.txt` for deeper extraction
- **Output:** Array of typed "stills" saved to database

### Step 3: Drafting
- **Input:** Stills + persona + brand voice + memory rules
- **Process:** Claude Opus 4.5 generates content:
  - **LinkedIn Posts** (3 variations default)
  - **Blog Articles** (1 default)
  - **Email Sequences** (3-email series)
- **Output:** Initial drafts with cited sources

### Step 4: Editing & Scoring
- **Audience Optimization:** Refine for target persona
- **Fact-checking:** Verify claims, flag concerns
- **Quality Scoring:** Rate on 4 dimensions (0-10):
  - Hook strength
  - Brand alignment
  - Clarity
  - Engagement potential
- **Output:** Final polished content with scores

---

## Key Features

### 1. Personas
Pre-built personas with customizable attributes:
- **General Audience** - Clear, accessible professional content
- **CEO Long-Term Care** - Executive-level, ROI-focused
- **Director of Nursing** - Clinical but empathetic
- **Marketing Director** - Strategic, creative

Custom personas support:
- Role, industry, company size
- Pain points and goals
- Tone preferences (formal/casual, data-heavy/story-focused)
- Content length preferences

### 2. Brand Voice
- Upload writing samples (blog posts, emails, social)
- AI analyzes patterns: vocabulary, sentence structure, tone
- Extracts "phrases to use" and "phrases to avoid"
- Applied automatically to all generated content

### 3. Memory Rules
Persistent rules applied across all content:
- **Avoid:** "Never use the word 'synergy'"
- **Prefer:** "Always mention our 100-year history"
- **Format:** "Use bullet points for lists"
- **Tone:** "Keep it conversational, not corporate"

### 4. Swipe Files & Style DNA
- Collect content examples you admire
- AI analyzes collection for patterns
- Extracts "Style DNA" (hooks, structures, techniques)
- Apply discovered patterns to your content

### 5. Content Library ("The Reserve")
- All extracted stills stored for reuse
- Filter by type, campaign, topic, persona
- Generate new content from selected stills
- Track usage frequency

### 6. Batch Processing
- Upload 2-10 files simultaneously
- Concurrent processing (configurable limit)
- Download results as ZIP
- Shared settings across batch

### 7. Content Calendar
- Schedule outputs for specific dates/times
- Platform-specific scheduling
- Status tracking (scheduled, published, cancelled)

### 8. Autopilot
- Monitor RSS feeds for new content
- Receive webhooks from external systems
- Auto-queue new items for processing
- Background scheduler with configurable intervals

### 9. Webhooks (Zapier Integration)
- Trigger events: job.complete, output.created, batch.complete
- HMAC signature verification
- Retry logic with exponential backoff
- Delivery tracking and logs

---

## API Endpoints Summary

| Category | Endpoints |
|----------|-----------|
| Auth | `/api/auth/register`, `/login`, `/logout`, `/me` |
| Upload | `/api/upload`, `/upload-text`, `/quick-distill` |
| Jobs | `/api/job/{id}/status`, `/job/{id}/results`, `/jobs` |
| Library | `/api/library`, `/library/add`, `/library/{id}`, `/generate-from-library` |
| Workshop | `/api/workshop`, `/workshop/{id}`, `/edit/{id}`, `/edit/{id}/ai-suggestions` |
| Personas | `/api/personas`, `/custom-personas`, `/personas/preview-voice` |
| Brand | `/api/brand-voice`, `/memory` |
| Batch | `/api/batch/upload`, `/batch/{id}/status`, `/batch/{id}/results` |
| Calendar | `/api/calendar`, `/calendar/schedule`, `/calendar/{id}` |
| Autopilot | `/api/autopilot/sources`, `/autopilot/items` |
| Webhooks | `/api/webhooks`, `/webhooks/{id}/test` |
| Swipes | `/api/swipes`, `/swipes/analyze`, `/swipes/style-dna` |
| Analytics | `/api/analytics/summary`, `/usage`, `/costs`, `/roi` |
| Admin | `/api/admin/dashboard`, `/prompts`, `/settings`, `/model-config` |

---

## Environment Variables

```env
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:6543/postgres

# AI APIs (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=...

# Optional
USE_OPENROUTER=true  # Use OpenRouter instead of direct Anthropic
DEBUG=false
ENVIRONMENT=production
UPLOAD_MAX_SIZE_MB=100
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password
ALLOWED_ORIGINS=https://yourdomain.com

# Railway (auto-set)
PORT=8000
RAILWAY_VOLUME_MOUNT_PATH=/data
```

---

## Development Notes

### Database Compatibility
The app supports both PostgreSQL and SQLite via `db_utils.py`:
- `format_query()` - Converts `?` placeholders to `$1, $2` for PostgreSQL
- `get_returning_clause()` - Handles RETURNING syntax differences
- `adapt_jsonb()` - Handles JSON serialization for PostgreSQL JSONB columns

### Rate Limits
- Registration: 500/hour (high for E2E testing)
- Login: 10/minute
- Upload: 10/hour
- Batch: 5/hour
- General API: 1000/hour

### Typical Processing Costs (per job)
- Transcription: ~$0.05
- Distillation: ~$0.10
- Drafting (Claude Opus): ~$2.00
- Editing: ~$0.05
- Fact-check + Scoring: ~$0.03
- **Total:** ~$2.23 per 1-hour video

### Testing
```bash
# Run E2E tests
pytest tests/test_e2e.py -v

# Run with coverage
pytest --cov=app tests/
```

---

## Known Patterns & Conventions

1. **All database operations use async/await** with `asyncpg` or `aiosqlite`
2. **Prompt templates are external files** in `data/prompts/` for easy editing
3. **Personas are JSON-configured** - system personas in `data/personas.json`, custom in database
4. **Quality scores are 0-10 scale** across 4 dimensions
5. **Job status flow:** uploading → transcribing → distilling → drafting → editing → complete
6. **Stills are typed:** insight, statistic, quote, story, actionable_advice, contrarian, framework
7. **All API responses follow consistent JSON structure** with error handling
