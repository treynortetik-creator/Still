"""Database setup and connection management."""
import aiosqlite
from pathlib import Path
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from app.config import get_settings

settings = get_settings()

# Ensure database directory exists
settings.database_dir.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = settings.database_dir / "contentmultiplier.db"


async def init_db():
    """Initialize the database with schema."""
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
                FOREIGN KEY (job_id) REFERENCES jobs(id),
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
                FOREIGN KEY (job_id) REFERENCES jobs(id)
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
                FOREIGN KEY (output_id) REFERENCES outputs(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
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
                FOREIGN KEY (output_id) REFERENCES outputs(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- Swipe File System
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

            -- Context Memory Commands
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

            -- Brand Voice Analysis
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

            -- Create indexes for common queries
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

            -- Custom Personas
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

            CREATE INDEX IF NOT EXISTS idx_personas_user ON personas(user_id);

            -- Batches for batch processing
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

            CREATE INDEX IF NOT EXISTS idx_batches_user ON batches(user_id);
            CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);

            -- Image Prompts for content outputs
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

            CREATE INDEX IF NOT EXISTS idx_image_prompts_output ON image_prompts(output_id);

            -- Webhooks for Zapier/external integrations
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

            CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id);
            CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);

            -- Content Calendar for scheduling
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

            CREATE INDEX IF NOT EXISTS idx_content_schedule_user ON content_schedule(user_id);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_date ON content_schedule(scheduled_date);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_status ON content_schedule(status);

            -- Autopilot Monitors for RSS/YouTube/Podcast feeds
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

            CREATE INDEX IF NOT EXISTS idx_autopilot_sources_user ON autopilot_sources(user_id);
            CREATE INDEX IF NOT EXISTS idx_autopilot_sources_active ON autopilot_sources(is_active, next_check);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_source ON autopilot_items(source_id);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_status ON autopilot_items(processing_status);

            -- AI Model Configuration for admin model selection
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

            CREATE INDEX IF NOT EXISTS idx_ai_model_config_service ON ai_model_config(service_name);

            -- Brand Voice Extended Configuration
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

            CREATE INDEX IF NOT EXISTS idx_brand_voice_config_user ON brand_voice_config(user_id);

            -- AI Editor Configuration for Workshop
            CREATE TABLE IF NOT EXISTS ai_editor_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Revoked Tokens for persistent token blacklist
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                token_hash TEXT PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires ON revoked_tokens(expires_at);

            -- Phase 2: Compound indexes for query optimization
            CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_outputs_job_type ON outputs(job_id, content_type);
            CREATE INDEX IF NOT EXISTS idx_outputs_job_status ON outputs(job_id, status);
            CREATE INDEX IF NOT EXISTS idx_content_schedule_user_date ON content_schedule(user_id, scheduled_date);
            CREATE INDEX IF NOT EXISTS idx_stills_job_type ON stills(job_id, still_type);
            CREATE INDEX IF NOT EXISTS idx_content_library_user_type ON content_library(user_id, entry_type);
            CREATE INDEX IF NOT EXISTS idx_autopilot_items_user_status ON autopilot_items(user_id, processing_status);
            CREATE INDEX IF NOT EXISTS idx_error_logs_type ON error_logs(user_id, error_type, created_at);
        """)

        await db.commit()

        # Migration: Rename atoms table to stills if old table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='atoms'"
        )
        if await cursor.fetchone() is not None:
            # Check if stills table is empty (new schema)
            cursor = await db.execute("SELECT COUNT(*) FROM stills")
            stills_count = (await cursor.fetchone())[0]

            if stills_count == 0:
                # Migrate data from atoms to stills
                await db.execute("""
                    INSERT INTO stills (id, job_id, user_id, still_type, content,
                        source_location, source_file, tags, persona_relevance,
                        quote_attribution, created_at, times_used, last_used)
                    SELECT id, job_id, user_id, atom_type, content,
                        source_location, source_file, tags, persona_relevance,
                        quote_attribution, created_at, times_used, last_used
                    FROM atoms
                """)
                await db.commit()

            # Drop old atoms table and its indexes
            await db.execute("DROP INDEX IF EXISTS idx_atoms_user_id")
            await db.execute("DROP INDEX IF EXISTS idx_atoms_job_id")
            await db.execute("DROP INDEX IF EXISTS idx_atoms_type")
            await db.execute("DROP TABLE IF EXISTS atoms")
            await db.commit()

        # Migration: Add workshop columns to outputs table if they don't exist
        cursor = await db.execute("PRAGMA table_info(outputs)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'status' not in columns:
            await db.execute("ALTER TABLE outputs ADD COLUMN status TEXT DEFAULT 'draft'")
        if 'edited_content' not in columns:
            await db.execute("ALTER TABLE outputs ADD COLUMN edited_content TEXT DEFAULT NULL")
        if 'last_edited' not in columns:
            await db.execute("ALTER TABLE outputs ADD COLUMN last_edited TIMESTAMP DEFAULT NULL")
        await db.commit()

        # Create default user if not exists
        cursor = await db.execute("SELECT id FROM users WHERE email = ?", ("default@contentmultiplier.com",))
        if await cursor.fetchone() is None:
            await db.execute(
                "INSERT INTO users (email, subscription_tier) VALUES (?, ?)",
                ("default@contentmultiplier.com", "pro")
            )
            await db.commit()

        # Migration: Add cascading deletes for stills, outputs, output_edits
        # Check if migration is needed by checking foreign key info
        cursor = await db.execute("PRAGMA foreign_key_list(stills)")
        fk_info = await cursor.fetchall()
        needs_cascade_migration = True
        for fk in fk_info:
            # fk[5] is on_delete action
            if fk[2] == 'jobs' and fk[5] == 'CASCADE':
                needs_cascade_migration = False
                break

        if needs_cascade_migration:
            # Temporarily disable foreign keys for migration
            await db.execute("PRAGMA foreign_keys = OFF")

            # Drop any leftover temp tables from partial migrations
            await db.execute("DROP TABLE IF EXISTS stills_new")
            await db.execute("DROP TABLE IF EXISTS outputs_new")
            await db.execute("DROP TABLE IF EXISTS output_edits_new")
            await db.execute("DROP TABLE IF EXISTS output_feedback_new")

            # Migrate stills table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stills_new (
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
                )
            """)
            # Get columns from existing stills table for dynamic migration
            cursor_stills = await db.execute("PRAGMA table_info(stills)")
            existing_stills_cols = [row[1] for row in await cursor_stills.fetchall()]
            stills_new_cols = ['id', 'job_id', 'user_id', 'still_type', 'content', 'source_location',
                               'source_file', 'tags', 'persona_relevance', 'quote_attribution',
                               'created_at', 'times_used', 'last_used', 'campaign_name', 'topics']
            stills_select_parts = []
            for col in stills_new_cols:
                if col in existing_stills_cols:
                    stills_select_parts.append(col)
                else:
                    stills_select_parts.append(f"NULL as {col}")
            stills_select = ", ".join(stills_select_parts)
            await db.execute(f"INSERT OR IGNORE INTO stills_new ({', '.join(stills_new_cols)}) SELECT {stills_select} FROM stills")
            await db.execute("DROP TABLE stills")
            await db.execute("ALTER TABLE stills_new RENAME TO stills")

            # Migrate outputs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS outputs_new (
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
                )
            """)
            # Get columns from the existing outputs table
            cursor_cols = await db.execute("PRAGMA table_info(outputs)")
            existing_cols = [row[1] for row in await cursor_cols.fetchall()]

            # Build dynamic INSERT statement based on existing columns
            # New table columns in order
            new_cols = [
                'id', 'job_id', 'content_type', 'variation_number', 'step1_draft',
                'step2_edited', 'step3_final', 'atoms_used', 'citations', 'warnings',
                'quality_scores', 'hook_variations', 'subject', 'preview_text',
                'email_day', 'email_purpose', 'sequence_name', 'user_edits', 'status',
                'edited_content', 'last_edited', 'created_at', 'campaign_name', 'topics'
            ]

            # Build column lists and values for migration
            select_parts = []
            for col in new_cols:
                if col in existing_cols:
                    select_parts.append(col)
                elif col == 'status':
                    select_parts.append("'draft' as status")
                elif col == 'user_edits':
                    select_parts.append("0 as user_edits")
                elif col == 'sequence_name':
                    select_parts.append("NULL as sequence_name")
                elif col in ('edited_content', 'last_edited'):
                    select_parts.append(f"NULL as {col}")
                else:
                    select_parts.append(f"NULL as {col}")

            select_clause = ", ".join(select_parts)
            await db.execute(f"INSERT OR IGNORE INTO outputs_new ({', '.join(new_cols)}) SELECT {select_clause} FROM outputs")
            await db.execute("DROP TABLE outputs")
            await db.execute("ALTER TABLE outputs_new RENAME TO outputs")

            # Migrate output_edits table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS output_edits_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    previous_content TEXT,
                    new_content TEXT NOT NULL,
                    edit_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (output_id) REFERENCES outputs(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await db.execute("INSERT OR IGNORE INTO output_edits_new SELECT * FROM output_edits")
            await db.execute("DROP TABLE output_edits")
            await db.execute("ALTER TABLE output_edits_new RENAME TO output_edits")

            # Migrate output_feedback table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS output_feedback_new (
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
                )
            """)
            await db.execute("INSERT OR IGNORE INTO output_feedback_new SELECT * FROM output_feedback")
            await db.execute("DROP TABLE output_feedback")
            await db.execute("ALTER TABLE output_feedback_new RENAME TO output_feedback")

            # Re-create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stills_user_id ON stills(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stills_job_id ON stills(job_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stills_type ON stills(still_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stills_job_type ON stills(job_id, still_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_outputs_job_type ON outputs(job_id, content_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_outputs_job_status ON outputs(job_id, status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_output_edits_output ON output_edits(output_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_output_feedback_output ON output_feedback(output_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_output_feedback_user ON output_feedback(user_id)")

            # Re-enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")
            await db.commit()

        # Migration: Add campaign_name and topics columns for campaign tagging
        cursor = await db.execute("PRAGMA table_info(stills)")
        stills_columns = [row[1] for row in await cursor.fetchall()]

        if 'campaign_name' not in stills_columns:
            await db.execute("ALTER TABLE stills ADD COLUMN campaign_name TEXT")
        if 'topics' not in stills_columns:
            await db.execute("ALTER TABLE stills ADD COLUMN topics JSON")

        cursor = await db.execute("PRAGMA table_info(outputs)")
        outputs_columns = [row[1] for row in await cursor.fetchall()]

        if 'campaign_name' not in outputs_columns:
            await db.execute("ALTER TABLE outputs ADD COLUMN campaign_name TEXT")
        if 'topics' not in outputs_columns:
            await db.execute("ALTER TABLE outputs ADD COLUMN topics JSON")

        cursor = await db.execute("PRAGMA table_info(content_library)")
        content_library_columns = [row[1] for row in await cursor.fetchall()]

        if 'campaign_name' not in content_library_columns:
            await db.execute("ALTER TABLE content_library ADD COLUMN campaign_name TEXT")
        if 'topics' not in content_library_columns:
            await db.execute("ALTER TABLE content_library ADD COLUMN topics JSON")

        await db.commit()

        # Create indexes for campaign_name on the three tables
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stills_campaign ON stills(campaign_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_outputs_campaign ON outputs(campaign_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_content_library_campaign ON content_library(campaign_name)")
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Get database connection as async context manager."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")
        # WAL mode for better concurrency (allows concurrent reads during writes)
        await db.execute("PRAGMA journal_mode = WAL")
        # Busy timeout: wait up to 5 seconds if database is locked
        await db.execute("PRAGMA busy_timeout = 5000")
        yield db
    finally:
        await db.close()


async def get_db_connection() -> aiosqlite.Connection:
    """Get a database connection (caller must close)."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("PRAGMA busy_timeout = 5000")
    return db


@asynccontextmanager
async def transaction():
    """
    Transaction context manager with automatic rollback on exception.

    Usage:
        async with transaction() as db:
            await db.execute(...)
            await db.execute(...)
            # Auto-commits on success, rolls back on exception
    """
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
