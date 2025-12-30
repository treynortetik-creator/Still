-- Migration: Add global_settings table for database-backed configuration
-- Run this in Supabase SQL Editor

-- Create global_settings table
CREATE TABLE IF NOT EXISTS global_settings (
    id SERIAL PRIMARY KEY,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    setting_type TEXT DEFAULT 'string',
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_global_settings_key ON global_settings(setting_key);

-- Insert default settings
INSERT INTO global_settings (setting_key, setting_value, setting_type, description)
VALUES
    ('use_openrouter', 'true', 'boolean', 'Whether to use OpenRouter for AI calls')
ON CONFLICT (setting_key) DO NOTHING;

-- Ensure ai_model_config table exists with correct schema
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
);

-- Create index for ai_model_config
CREATE INDEX IF NOT EXISTS idx_ai_model_config_service ON ai_model_config(service_name);

-- Insert default model configurations
INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
VALUES
    ('transcription', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true),
    ('distillation', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true),
    ('atomization', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true),
    ('drafting', 'google/gemini-3-flash-preview', 'Gemini 3 Flash Preview', true),
    ('editing', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true),
    ('factcheck', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash', true),
    ('workshop_ai_edit', 'google/gemini-2.5-flash-preview', 'Gemini 2.5 Flash Preview', true)
ON CONFLICT (service_name) DO NOTHING;
