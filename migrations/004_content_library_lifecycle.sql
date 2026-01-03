-- Migration: Add lifecycle fields to content_library table
-- These fields mirror the stills table lifecycle fields for Reserve management
-- Run this in Supabase SQL Editor

-- Add status column with CHECK constraint
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

ALTER TABLE content_library
ADD CONSTRAINT content_library_status_check
CHECK (status IS NULL OR status IN ('active', 'evergreen', 'needs_review', 'retired'));

-- Add best_formats as TEXT array (matching stills table)
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS best_formats TEXT[];

-- Add funnel_stage with CHECK constraint
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS funnel_stage TEXT;

ALTER TABLE content_library
ADD CONSTRAINT content_library_funnel_stage_check
CHECK (funnel_stage IS NULL OR funnel_stage IN ('awareness', 'consideration', 'decision'));

-- Add expiration_type with CHECK constraint
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS expiration_type TEXT;

ALTER TABLE content_library
ADD CONSTRAINT content_library_expiration_type_check
CHECK (expiration_type IS NULL OR expiration_type IN ('date_bound', 'event_bound', 'evergreen'));

-- Add expiration_date
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS expiration_date DATE;

-- Add performance with CHECK constraint
ALTER TABLE content_library
ADD COLUMN IF NOT EXISTS performance TEXT DEFAULT 'untested';

ALTER TABLE content_library
ADD CONSTRAINT content_library_performance_check
CHECK (performance IS NULL OR performance IN ('high', 'medium', 'low', 'untested'));

-- Create indexes for common filter/sort operations
CREATE INDEX IF NOT EXISTS idx_content_library_status ON content_library(status);
CREATE INDEX IF NOT EXISTS idx_content_library_funnel_stage ON content_library(funnel_stage);
CREATE INDEX IF NOT EXISTS idx_content_library_expiration_date ON content_library(expiration_date);
CREATE INDEX IF NOT EXISTS idx_content_library_times_used ON content_library(times_used);
