-- Migration: Add language_level column to personas table
-- Run this on both SQLite and PostgreSQL
ALTER TABLE personas ADD COLUMN language_level VARCHAR(50) DEFAULT 'Professional';
