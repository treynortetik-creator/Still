-- Migration: Add distillation_pass2 model config for multi-pass extraction
-- Run this in Supabase SQL Editor

-- Insert default model configuration for distillation_pass2
INSERT INTO ai_model_config (service_name, model_id, display_name, is_active)
VALUES
    ('distillation_pass2', 'google/gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite', true)
ON CONFLICT (service_name) DO NOTHING;
