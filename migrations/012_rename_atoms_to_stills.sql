-- Migration: Standardize 'atoms' terminology to 'stills'
-- This migration renames the atoms_used column to stills_used in the outputs table
-- Run this in Supabase SQL Editor

-- Rename column in outputs table
ALTER TABLE outputs RENAME COLUMN atoms_used TO stills_used;

-- Note: This migration only handles the database column rename.
-- Application code has been updated to use 'stills_used' throughout.
-- Backwards compatibility for API responses is maintained where needed.
