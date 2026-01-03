"""Database setup and connection management.

Supports both PostgreSQL (Supabase) and SQLite (local development).
"""
import ssl
import socket
import aiosqlite
import asyncpg
from pathlib import Path
from typing import AsyncGenerator, Optional, Union
from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs, unquote

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


def _parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL into connection parameters."""
    parsed = urlparse(url)

    # Extract components
    params = {
        "user": parsed.username or "postgres",
        "password": unquote(parsed.password) if parsed.password else None,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") or "postgres",
    }

    # Parse query string for additional options
    if parsed.query:
        query_params = parse_qs(parsed.query)
        for key, values in query_params.items():
            if values:
                params[key] = values[0]

    return params


async def init_postgres_pool():
    """Initialize PostgreSQL connection pool for Supabase."""
    global _pg_pool
    if _pg_pool is None:
        # Create SSL context for Supabase connection
        # Supabase requires SSL but uses self-signed certs, so we disable verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Parse the database URL to get individual components
        db_params = _parse_database_url(settings.database_url)
        host = db_params["host"]
        port = db_params["port"]

        print(f"Attempting to connect to {host}:{port}")

        # Resolve hostname to IPv4 to avoid IPv6 issues on some platforms
        try:
            # Get IPv4 address explicitly
            ipv4_addr = socket.gethostbyname(host)
            print(f"Resolved {host} to IPv4: {ipv4_addr}")
        except socket.gaierror as e:
            print(f"Warning: Could not resolve {host}: {e}")
            ipv4_addr = host  # Fall back to hostname

        try:
            _pg_pool = await asyncpg.create_pool(
                host=ipv4_addr,
                port=port,
                user=db_params["user"],
                password=db_params["password"],
                database=db_params["database"],
                min_size=2,  # Reduced for Railway/Supabase free tier limits
                max_size=10,  # Supabase free tier has connection limits
                statement_cache_size=0,  # Required for Supabase/PgBouncer
                ssl=ssl_context,  # Required for Supabase
                command_timeout=60,  # 60 second timeout for commands
                timeout=30,  # 30 second connection timeout
            )
            print(f"PostgreSQL pool initialized (min=2, max=10)")
        except Exception as e:
            print(f"Failed to initialize PostgreSQL pool: {e}")
            print(f"Connection details: host={ipv4_addr}, port={port}, user={db_params['user']}, database={db_params['database']}")
            raise
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

    For PostgreSQL: Creates tables if they don't exist, then verifies connection
    For SQLite: Creates tables if they don't exist
    """
    if settings.use_postgres:
        # Log connection attempt (mask password)
        db_url = settings.database_url
        if db_url:
            # Mask password in logs
            import re
            masked_url = re.sub(r':([^@]+)@', ':****@', db_url)
            print(f"Connecting to PostgreSQL: {masked_url}")
        else:
            print("ERROR: DATABASE_URL is empty but use_postgres is True!")
            raise ValueError("DATABASE_URL environment variable is not set")

        # PostgreSQL - create tables and verify connection
        try:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                # Test connection
                result = await conn.fetchval("SELECT 1")
                print(f"PostgreSQL connection verified (result: {result})")

                # Create tables if they don't exist
                await _init_postgres_tables(conn)
        except Exception as e:
            print(f"ERROR: Failed to connect to PostgreSQL: {e}")
            print("Check that DATABASE_URL is correct and Supabase is accessible")
            raise
    else:
        # SQLite - create tables
        print("Using SQLite database (local development mode)")
        await _init_sqlite_db()


async def _init_postgres_tables(conn: asyncpg.Connection):
    """Initialize PostgreSQL database with schema (creates tables if not exist)."""
    print("Checking/creating PostgreSQL tables...")

    # Create all tables using PostgreSQL syntax
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            subscription_tier TEXT DEFAULT 'free',
            credits_remaining INTEGER DEFAULT 0,
            total_cost_incurred FLOAT DEFAULT 0.0,
            byok_enabled BOOLEAN DEFAULT false,
            api_keys JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            last_login TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_hash TEXT PRIMARY KEY,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            action_type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS error_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            job_id TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT,
            stack_trace TEXT,
            context TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL,
            original_filename TEXT,
            file_type TEXT,
            file_size INTEGER,
            target_persona TEXT,
            asset_types JSONB,
            asset_quantities JSONB,
            processing_mode TEXT DEFAULT 'autopilot',
            campaign_name TEXT,
            magic_words TEXT,
            generate_image_prompts BOOLEAN DEFAULT FALSE,
            current_step TEXT,
            progress INTEGER DEFAULT 0,
            transcript TEXT,
            cleaned_transcript TEXT,
            source_summary TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            cost_incurred FLOAT DEFAULT 0.0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id SERIAL PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            core_narratives JSONB NOT NULL,
            statistics JSONB NOT NULL,
            quotable_moments JSONB NOT NULL,
            primary_pain_point TEXT NOT NULL,
            the_promise TEXT NOT NULL,
            objections_qa JSONB,
            key_visuals JSONB,
            funnel_stage TEXT NOT NULL CHECK(funnel_stage IN ('awareness', 'consideration', 'decision')),
            review_date DATE NOT NULL,
            is_approved BOOLEAN DEFAULT FALSE,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Add source_id to jobs if not exists
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='jobs' AND column_name='source_id') THEN
                ALTER TABLE jobs ADD COLUMN source_id INTEGER REFERENCES sources(id);
            END IF;
        END $$;
    """)

    # Add auto_approve_source to jobs if not exists
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='jobs' AND column_name='auto_approve_source') THEN
                ALTER TABLE jobs ADD COLUMN auto_approve_source BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS stills (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            still_type TEXT NOT NULL,
            content TEXT NOT NULL,
            source_location TEXT,
            source_file TEXT,
            tags JSONB,
            persona_relevance JSONB,
            quote_attribution TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            times_used INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            campaign_name TEXT,
            topics JSONB
        )
    """)

    # Add source_id to stills if not exists
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='stills' AND column_name='source_id') THEN
                ALTER TABLE stills ADD COLUMN source_id INTEGER REFERENCES sources(id);
            END IF;
        END $$;
    """)

    # Add job_id to content_library if not exists
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='content_library' AND column_name='job_id') THEN
                ALTER TABLE content_library ADD COLUMN job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS outputs (
            id SERIAL PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            content_type TEXT NOT NULL,
            variation_number INTEGER,
            step1_draft TEXT,
            step2_edited TEXT,
            step3_final TEXT,
            atoms_used JSONB,
            citations JSONB,
            warnings JSONB,
            quality_scores JSONB,
            hook_variations JSONB,
            subject TEXT,
            preview_text TEXT,
            email_day INTEGER,
            email_purpose TEXT,
            sequence_name TEXT,
            user_edits INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            edited_content TEXT DEFAULT NULL,
            last_edited TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            campaign_name TEXT,
            topics JSONB
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS content_library (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            entry_type TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT,
            source_timestamp TEXT,
            speaker TEXT,
            date_added TIMESTAMP DEFAULT NOW(),
            tags JSONB,
            persona_relevance JSONB,
            times_used INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            user_notes TEXT,
            campaign_name TEXT,
            topics JSONB,
            job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
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
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS output_feedback (
            id SERIAL PRIMARY KEY,
            output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            feedback TEXT NOT NULL CHECK(feedback IN ('thumbs_up', 'thumbs_down')),
            comment TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(output_id, user_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS output_edits (
            id SERIAL PRIMARY KEY,
            output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            previous_content TEXT,
            new_content TEXT NOT NULL,
            edit_note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS swipe_files (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            source_url TEXT,
            source_type TEXT DEFAULT 'general',
            title TEXT,
            tags JSONB,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS swipe_analysis (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            analysis_type TEXT NOT NULL,
            patterns JSONB NOT NULL,
            summary TEXT,
            swipe_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_rules (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            rule_type TEXT NOT NULL,
            rule_text TEXT NOT NULL,
            is_active BOOLEAN DEFAULT true,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS brand_voice_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
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
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS brand_voice_samples (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            profile_id INTEGER NOT NULL REFERENCES brand_voice_profiles(id),
            content TEXT NOT NULL,
            content_type TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS personas (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            industry TEXT,
            pain_points JSONB NOT NULL,
            goals JSONB NOT NULL,
            tone_preferences JSONB,
            content_preferences JSONB,
            is_default BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'pending',
            job_ids JSONB NOT NULL,
            total_jobs INTEGER NOT NULL,
            completed_jobs INTEGER DEFAULT 0,
            failed_jobs INTEGER DEFAULT 0,
            settings JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            total_cost FLOAT DEFAULT 0.0
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS image_prompts (
            id SERIAL PRIMARY KEY,
            output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
            prompt_text TEXT NOT NULL,
            platform TEXT NOT NULL,
            dimensions TEXT NOT NULL,
            style_modifiers TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            secret_key TEXT NOT NULL,
            trigger_events JSONB NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, url)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id SERIAL PRIMARY KEY,
            webhook_id INTEGER NOT NULL REFERENCES webhooks(id),
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            response_status INTEGER,
            response_body TEXT,
            attempts INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS content_schedule (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
            scheduled_date DATE NOT NULL,
            scheduled_time TIME DEFAULT '09:00:00',
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(output_id, platform)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_sources (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_name TEXT NOT NULL,
            check_frequency TEXT DEFAULT 'daily',
            last_checked TIMESTAMP,
            next_check TIMESTAMP,
            is_active BOOLEAN DEFAULT true,
            target_persona TEXT,
            asset_types JSONB DEFAULT '["linkedin"]',
            items_processed INTEGER DEFAULT 0,
            last_error TEXT,
            error_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_items (
            id SERIAL PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES autopilot_sources(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            item_guid TEXT NOT NULL,
            item_title TEXT,
            item_url TEXT NOT NULL,
            item_published TIMESTAMP,
            job_id TEXT REFERENCES jobs(id),
            processing_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(source_id, item_guid)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_model_config (
            id SERIAL PRIMARY KEY,
            service_name TEXT NOT NULL UNIQUE,
            model_id TEXT NOT NULL,
            display_name TEXT,
            is_active BOOLEAN DEFAULT true,
            cost_per_1k_input FLOAT DEFAULT 0.0,
            cost_per_1k_output FLOAT DEFAULT 0.0,
            max_tokens INTEGER DEFAULT 4096,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS brand_voice_config (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
            company_name TEXT,
            industry TEXT,
            tone_linkedin TEXT,
            tone_blog TEXT,
            tone_email TEXT,
            tone_twitter TEXT,
            core_principles JSONB,
            phrases_to_use JSONB,
            phrases_to_avoid JSONB,
            vocabulary_level TEXT DEFAULT 'professional',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_editor_config (
            id SERIAL PRIMARY KEY,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS global_settings (
            id SERIAL PRIMARY KEY,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            setting_type TEXT DEFAULT 'string',
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create indexes (PostgreSQL syntax)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_stills_user_id ON stills(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_stills_job_id ON stills(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_stills_type ON stills(still_type)",
        "CREATE INDEX IF NOT EXISTS idx_content_library_user_id ON content_library(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_content_library_type ON content_library(entry_type)",
        "CREATE INDEX IF NOT EXISTS idx_rate_limits_user ON rate_limits(user_id, action_type, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_error_logs_user ON error_logs(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_output_feedback_output ON output_feedback(output_id)",
        "CREATE INDEX IF NOT EXISTS idx_output_feedback_user ON output_feedback(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_output_edits_output ON output_edits(output_id)",
        "CREATE INDEX IF NOT EXISTS idx_swipe_files_user ON swipe_files(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_swipe_analysis_user ON swipe_analysis(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_memory_rules_user ON memory_rules(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_brand_voice_profiles_user ON brand_voice_profiles(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_brand_voice_samples_profile ON brand_voice_samples(profile_id)",
        "CREATE INDEX IF NOT EXISTS idx_personas_user ON personas(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_batches_user ON batches(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status)",
        "CREATE INDEX IF NOT EXISTS idx_image_prompts_output ON image_prompts(output_id)",
        "CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id)",
        "CREATE INDEX IF NOT EXISTS idx_content_schedule_user ON content_schedule(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_content_schedule_date ON content_schedule(scheduled_date)",
        "CREATE INDEX IF NOT EXISTS idx_content_schedule_status ON content_schedule(status)",
        "CREATE INDEX IF NOT EXISTS idx_autopilot_sources_user ON autopilot_sources(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_autopilot_sources_active ON autopilot_sources(is_active, next_check)",
        "CREATE INDEX IF NOT EXISTS idx_autopilot_items_source ON autopilot_items(source_id)",
        "CREATE INDEX IF NOT EXISTS idx_autopilot_items_status ON autopilot_items(processing_status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_model_config_service ON ai_model_config(service_name)",
        "CREATE INDEX IF NOT EXISTS idx_brand_voice_config_user ON brand_voice_config(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires ON revoked_tokens(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_global_settings_key ON global_settings(setting_key)",
        "CREATE INDEX IF NOT EXISTS idx_sources_job ON sources(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sources_approved ON sources(is_approved)",
        "CREATE INDEX IF NOT EXISTS idx_stills_source ON stills(source_id)",
        "CREATE INDEX IF NOT EXISTS idx_content_library_job ON content_library(job_id)",
    ]

    for idx_sql in indexes:
        await conn.execute(idx_sql)

    # Create default user if not exists
    existing = await conn.fetchval(
        "SELECT id FROM users WHERE email = $1",
        "default@contentmultiplier.com"
    )
    if existing is None:
        await conn.execute(
            "INSERT INTO users (email, subscription_tier) VALUES ($1, $2)",
            "default@contentmultiplier.com", "pro"
        )

    print("PostgreSQL tables initialized")


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
                generate_image_prompts INTEGER DEFAULT 0,
                current_step TEXT,
                progress INTEGER DEFAULT 0,
                transcript TEXT,
                cleaned_transcript TEXT,
                source_summary TEXT,
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

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                core_narratives JSON NOT NULL,
                statistics JSON NOT NULL,
                quotable_moments JSON NOT NULL,
                primary_pain_point TEXT NOT NULL,
                the_promise TEXT NOT NULL,
                objections_qa JSON,
                key_visuals JSON,
                funnel_stage TEXT NOT NULL CHECK(funnel_stage IN ('awareness', 'consideration', 'decision')),
                review_date DATE NOT NULL,
                is_approved BOOLEAN DEFAULT 0,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
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
                job_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
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

            CREATE TABLE IF NOT EXISTS global_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                setting_type TEXT DEFAULT 'string',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            CREATE INDEX IF NOT EXISTS idx_global_settings_key ON global_settings(setting_key);
            CREATE INDEX IF NOT EXISTS idx_sources_job ON sources(job_id);
            CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id);
            CREATE INDEX IF NOT EXISTS idx_sources_approved ON sources(is_approved);
            CREATE INDEX IF NOT EXISTS idx_stills_source ON stills(source_id);
            CREATE INDEX IF NOT EXISTS idx_content_library_job ON content_library(job_id);
        """)

        await db.commit()

        # Migrate existing tables - add new columns if they don't exist
        cursor = await db.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'source_id' not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN source_id INTEGER REFERENCES sources(id)")

        if 'auto_approve_source' not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN auto_approve_source INTEGER DEFAULT 0")

        cursor = await db.execute("PRAGMA table_info(stills)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'source_id' not in columns:
            await db.execute("ALTER TABLE stills ADD COLUMN source_id INTEGER REFERENCES sources(id)")

        cursor = await db.execute("PRAGMA table_info(content_library)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'job_id' not in columns:
            await db.execute("ALTER TABLE content_library ADD COLUMN job_id TEXT REFERENCES jobs(id)")

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
