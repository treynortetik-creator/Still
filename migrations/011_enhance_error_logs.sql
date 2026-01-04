-- Migration: Enhance error_logs table with additional columns for comprehensive error tracking
-- Run this after the table is auto-created by admin.py, or modify the CREATE in admin.py

-- Add new columns if they don't exist (PostgreSQL syntax)
DO $$
BEGIN
    -- Add source column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'error_logs' AND column_name = 'source') THEN
        ALTER TABLE error_logs ADD COLUMN source TEXT DEFAULT 'backend';
    END IF;

    -- Add endpoint column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'error_logs' AND column_name = 'endpoint') THEN
        ALTER TABLE error_logs ADD COLUMN endpoint TEXT;
    END IF;

    -- Add additional_context column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'error_logs' AND column_name = 'additional_context') THEN
        ALTER TABLE error_logs ADD COLUMN additional_context JSONB;
    END IF;
END $$;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_source ON error_logs(source);
CREATE INDEX IF NOT EXISTS idx_error_logs_error_type ON error_logs(error_type);
