"""Database setup and connection management.

Supports both PostgreSQL (Supabase) and SQLite (local development).
"""
import aiosqlite
import asyncpg
from pathlib import Path
from typing import AsyncGenerator, Optional, Union
from contextlib import asynccontextmanager

from app.config import get_settings

settings = get_settings()

# PostgreSQL connection pool (initialized on startup)
_pg_pool: Optional[asyncpg.Pool] = None

# SQLite database path (for local development fallback)
if not settings.use_postgres:
    settings.database_dir.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH = settings.database_dir / "contentmultiplier.db"
else:
    DATABASE_PATH = None


async def init_postgres_pool():
    """Initialize PostgreSQL connection pool for Supabase."""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20,
            statement_cache_size=0,  # Required for Supabase/PgBouncer
        )
    return _pg_pool


async def close_postgres_pool():
    """Close PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None


async def get_pg_pool() -> asyncpg.Pool:
    """Get the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        await init_postgres_pool()
    return _pg_pool


async def init_db():
    """Initialize the database.

    For PostgreSQL: Just verifies connection (schema created via Supabase dashboard)
    For SQLite: Creates tables if they don't exist
    """
    if settings.use_postgres:
        # PostgreSQL - just verify connection works
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            # Test connection
            await conn.fetchval("SELECT 1")
            print("PostgreSQL connection verified")
    else:
        # SQLite - create tables
        await _init_sqlite_db()


async def _init_sqlite_db():
    """Initialize SQLite database with schema (for local development)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")

        # Create tables
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                subscription_tier TEXT DEFAULT 'free',
                credits_remaining INTEGER DEFAULT 0,
                total_cost_incurred REAL DEFAULT 0.0,
                byok_enabled BOOLEAN DEFAULT 0,
                api_keys JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS revoked_tokens (
                token_hash TEXT PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                job_id TEXT,
                error_type TEXT NOT NULL,
                error_message TEXT,
                stack_trace TEXT,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                original_filename TEXT,
                file_type TEXT,
                file_size INTEGER,
                target_persona TEXT,
                asset_types JSON,
                asset_quantities JSON,
                processing_mode TEXT DEFAULT 'autopilot',
                campaign_name TEXT,
                magic_words TEXT,
                current_step TEXT,
                progress INTEGER DEFAULT 0,
                transcript TEXT,
                cleaned_transcript TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                cost_incurred REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS stills (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                still_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_location TEXT,
                source_file TEXT,
                tags JSON,
                persona_relevance JSON,
                quote_attribution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_used INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                campaign_name TEXT,
                topics JSON,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                variation_number INTEGER,
                step1_draft TEXT,
                step2_edited TEXT,
                step3_final TEXT,
                atoms_used JSON,
                citations JSON,
                warnings JSON,
                quality_scores JSON,
                hook_variations JSON,
                subject TEXT,
                preview_text TEXT,
                email_day INTEGER,
                email_purpose TEXT,
                sequence_name TEXT,
                user_edits INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                edited_content TEXT DEFAULT NULL,
                last_edited TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                campaign_name TEXT,
                topics JSON,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS content_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                source_timestamp TEXT,
                speaker TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags JSON,
                persona_relevance JSON,
                times_used INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                user_notes TEXT,
                campaign_name TEXT,
                topics JSON,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE NOT NULL,
                model TEXT NOT NULL,
                max_tokens INTEGER DEFAULT 4000,
                prompt_content TEXT NOT NULL,
                variables JSON,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS output_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                output_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                feedback TEXT NOT NULL CHECK(feedback IN ('thumbs_up', 'thumbs_down')),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(output_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS output_edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                output_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                previous_content TEXT,
                new_content TEXT NOT NULL,
                edit_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS swipe_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                source_url TEXT,
                source_type TEXT DEFAULT 'general',
                title TEXT,
                tags JSON,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS swipe_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                patterns JSON NOT NULL,
                summary TEXT,
                swipe_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS memory_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                rule_type TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS brand_voice_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_name TEXT DEFAULT 'Primary Voice',
                vocabulary_patterns JSON,
                sentence_structure JSON,
                tone_markers JSON,
                phrases_to_use JSON,
                phrases_to_avoid JSON,
                overall_summary TEXT,
                sample_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS brand_voice_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (profile_id) REFERENCES brand_voice_profiles(id)
            );

            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                industry TEXT,
                pain_points JSON NOT NULL,
                goals JSON NOT NULL,
                tone_preferences JSON,
                content_preferences JSON,
                is_default BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                job_ids JSON NOT NULL,
                total_jobs INTEGER NOT NULL,
                completed_jobs INTEGER DEFAULT 0,
                failed_jobs INTEGER DEFAULT 0,
                settings JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                total_cost REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS image_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                output_id INTEGER NOT NULL,
                prompt_text TEXT NOT NULL,
                platform TEXT NOT NULL,
                dimensions TEXT NOT NULL,
                style_modifiers TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                secret_key TEXT NOT NULL,
                trigger_events JSON NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, url)
            );

            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload JSON NOT NULL,
                response_status INTEGER,
                response_body TEXT,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (webhook_id) REFERENCES webhooks(id)
            );

            CREATE TABLE IF NOT EXISTS content_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                output_id INTEGER NOT NULL,
                scheduled_date DATE NOT NULL,
                scheduled_time TIME DEFAULT '09:00:00',
                platform TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE,
                UNIQUE(output_id, platform)
            );

            CREATE TABLE IF NOT EXISTS autopilot_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                check_frequency TEXT DEFAULT 'daily',
                last_checked TIMESTAMP,
                next_check TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                target_persona TEXT,
                asset_types JSON DEFAULT '["linkedin"]',
                items_processed INTEGER DEFAULT 0,
                last_error TEXT,
                error_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS autopilot_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                item_guid TEXT NOT NULL,
                item_title TEXT,
                item_url TEXT NOT NULL,
                item_published TIMESTAMP,
                job_id TEXT,
                processing_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES autopilot_sources(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id),
                UNIQUE(source_id, item_guid)
            );

            CREATE TABLE IF NOT EXISTS ai_model_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL UNIQUE,
                model_id TEXT NOT NULL,
                display_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                cost_per_1k_input REAL DEFAULT 0.0,
                cost_per_1k_output REAL DEFAULT 0.0,
                max_tokens INTEGER DEFAULT 4096,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS brand_voice_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                company_name TEXT,
                industry TEXT,
                tone_linkedin TEXT,
                tone_blog TEXT,
                tone_email TEXT,
                tone_twitter TEXT,
                core_principles JSON,
                phrases_to_use JSON,
                phrases_to_avoid JSON,
                vocabulary_level TEXT DEFAULT 'professional',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS ai_editor_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_stills_user_id ON stills(user_id);
            CREATE INDEX IF NOT EXISTS idx_stills_job_id ON stills(job_id);
            CREATE INDEX IF NOT EXISTS idx_stills_type ON stills(still_type);
            CREATE INDEX IF NOT EXISTS idx_content_library_user_id ON content_library(user_id);
            CREATE INDEX IF NOT EXISTS idx_content_library_type ON content_library(entry_type);
            CREATE INDEX IF NOT EXISTS idx_rate_limits_user ON rate_limits(user_id, action_type, timestamp);
            CREATE INDEX IF NOT EXISTS idx_error_logs_user ON error_logs(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_output_feedback_output ON output_feedback(output_id);
            CREATE INDEX IF NOT EXISTS idx_output_feedback_user ON output_feedback(user_id);
            CREATE INDEX IF NOT EXISTS idx_output_edits_output ON output_edits(output_id);
            CREATE INDEX IF NOT EXISTS idx_swipe_files_user ON swipe_files(user_id);
            CREATE INDEX IF NOT EXISTS idx_swipe_analysis_user ON swipe_analysis(user_id);
            CREATE INDEX IF NOT EXISTS idx_memory_rules_user ON memory_rules(user_id, is_active);
            CREATE INDEX IF NOT EXISTS idx_brand_voice_profiles_user ON brand_voice_profiles(user_id);
            CREATE INDEX IF NOT EXISTS idx_brand_voice_samples_profile ON brand_voice_samples(profile_id);
            CREATE INDEX IF NOT EXISTS idx_personas_user ON personas(user_id);
            CREATE INDEX IF NOT EXISTS idx_batches_user ON batches(user_id);
            CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
            CREATE INDEX IF NOT EXISTS idx_image_prompts_output ON image_prompts(output_id);
            CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id);
            CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_user ON content_schedule(user_id);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_date ON content_schedule(scheduled_date);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_status ON content_schedule(status);
            CREATE INDEX IF NOT EXISTS idx_autopilot_sources_user ON autopilot_sources(user_id);
            CREATE INDEX IF NOT EXISTS idx_autopilot_sources_active ON autopilot_sources(is_active, next_check);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_source ON autopilot_items(source_id);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_status ON autopilot_items(processing_status);
            CREATE INDEX IF NOT EXISTS idx_ai_model_config_service ON ai_model_config(service_name);
            CREATE INDEX IF NOT EXISTS idx_brand_voice_config_user ON brand_voice_config(user_id);
            CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires ON revoked_tokens(expires_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_outputs_job_type ON outputs(job_id, content_type);
            CREATE INDEX IF NOT EXISTS idx_outputs_job_status ON outputs(job_id, status);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_user_date ON content_schedule(user_id, scheduled_date);
            CREATE INDEX IF NOT EXISTS idx_stills_job_type ON stills(job_id, still_type);
            CREATE INDEX IF NOT EXISTS idx_content_library_user_type ON content_library(user_id, entry_type);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_user_status ON autopilot_items(user_id, processing_status);
            CREATE INDEX IF NOT EXISTS idx_error_logs_type ON error_logs(user_id, error_type, created_at);
            CREATE INDEX IF NOT EXISTS idx_stills_campaign ON stills(campaign_name);
            CREATE INDEX IF NOT EXISTS idx_outputs_campaign ON outputs(campaign_name);
            CREATE INDEX IF NOT EXISTS idx_content_library_campaign ON content_library(campaign_name);
        """)

        await db.commit()

        # Create default user if not exists
        cursor = await db.execute("SELECT id FROM users WHERE email = ?", ("default@contentmultiplier.com",))
        if await cursor.fetchone() is None:
            await db.execute(
                "INSERT INTO users (email, subscription_tier) VALUES (?, ?)",
                ("default@contentmultiplier.com", "pro")
            )
            await db.commit()


# =============================================================================
# Database Context Managers - Unified interface for both PostgreSQL and SQLite
# =============================================================================

@asynccontextmanager
async def get_db() -> AsyncGenerator[Union[asyncpg.Connection, aiosqlite.Connection], None]:
    """Get database connection as async context manager.

    Works for both PostgreSQL and SQLite.
    """
    if settings.use_postgres:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            yield conn
    else:
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            yield db
        finally:
            await db.close()


async def get_db_connection() -> Union[asyncpg.Connection, aiosqlite.Connection]:
    """Get a database connection (caller must close).

    For PostgreSQL: Returns a connection from the pool
    For SQLite: Returns a new connection
    """
    if settings.use_postgres:
        pool = await get_pg_pool()
        return await pool.acquire()
    else:
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA busy_timeout = 5000")
        return db


async def release_db_connection(conn: Union[asyncpg.Connection, aiosqlite.Connection]):
    """Release a database connection back to pool or close it."""
    if settings.use_postgres:
        pool = await get_pg_pool()
        await pool.release(conn)
    else:
        await conn.close()


@asynccontextmanager
async def transaction():
    """Transaction context manager with automatic rollback on exception.

    Usage:
        async with transaction() as db:
            await db.execute(...)
            await db.execute(...)
            # Auto-commits on success, rolls back on exception
    """
    if settings.use_postgres:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    else:
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
