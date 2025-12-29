-- PostgreSQL Schema for ContentMultiplier
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/tvlvnplhybumuoiflthb/sql

-- =============================================================================
-- TABLES
-- =============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
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
);

-- Revoked tokens for logout/token invalidation
CREATE TABLE IF NOT EXISTS revoked_tokens (
    token_hash TEXT PRIMARY KEY,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP DEFAULT NOW()
);

-- Rate limiting
CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    action_type TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Error logs
CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    job_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    stack_trace TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Jobs
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
    current_step TEXT,
    progress INTEGER DEFAULT 0,
    transcript TEXT,
    cleaned_transcript TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    cost_incurred FLOAT DEFAULT 0.0
);

-- Stills (content atoms)
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
);

-- Outputs (generated content)
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
);

-- Content library
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
    topics JSONB
);

-- Prompt templates
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
);

-- Output feedback
CREATE TABLE IF NOT EXISTS output_feedback (
    id SERIAL PRIMARY KEY,
    output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback TEXT NOT NULL CHECK(feedback IN ('thumbs_up', 'thumbs_down')),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(output_id, user_id)
);

-- Output edits
CREATE TABLE IF NOT EXISTS output_edits (
    id SERIAL PRIMARY KEY,
    output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    previous_content TEXT,
    new_content TEXT NOT NULL,
    edit_note TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Swipe files
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
);

-- Swipe analysis
CREATE TABLE IF NOT EXISTS swipe_analysis (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    analysis_type TEXT NOT NULL,
    patterns JSONB NOT NULL,
    summary TEXT,
    swipe_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Memory rules
CREATE TABLE IF NOT EXISTS memory_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    rule_type TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Brand voice profiles
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
);

-- Brand voice samples
CREATE TABLE IF NOT EXISTS brand_voice_samples (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    profile_id INTEGER NOT NULL REFERENCES brand_voice_profiles(id),
    content TEXT NOT NULL,
    content_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Personas
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
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Batches
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
);

-- Image prompts
CREATE TABLE IF NOT EXISTS image_prompts (
    id SERIAL PRIMARY KEY,
    output_id INTEGER NOT NULL REFERENCES outputs(id) ON DELETE CASCADE,
    prompt_text TEXT NOT NULL,
    platform TEXT NOT NULL,
    dimensions TEXT NOT NULL,
    style_modifiers TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    trigger_events JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, url)
);

-- Webhook deliveries
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER NOT NULL REFERENCES webhooks(id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Content schedule
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
);

-- Autopilot sources
CREATE TABLE IF NOT EXISTS autopilot_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    check_frequency TEXT DEFAULT 'daily',
    last_checked TIMESTAMP,
    next_check TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    target_persona TEXT,
    asset_types JSONB DEFAULT '["linkedin"]',
    items_processed INTEGER DEFAULT 0,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Autopilot items
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
);

-- AI model config
CREATE TABLE IF NOT EXISTS ai_model_config (
    id SERIAL PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,
    model_id TEXT NOT NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    cost_per_1k_input FLOAT DEFAULT 0.0,
    cost_per_1k_output FLOAT DEFAULT 0.0,
    max_tokens INTEGER DEFAULT 4096,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Brand voice config
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
);

-- AI editor config
CREATE TABLE IF NOT EXISTS ai_editor_config (
    id SERIAL PRIMARY KEY,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

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
