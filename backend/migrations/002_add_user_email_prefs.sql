-- Migration 002: Add per-user email preferences
-- Moves hardcoded font/size mappings from code to database

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_font TEXT DEFAULT 'sans-serif';
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_font_size TEXT DEFAULT '15px';
ALTER TABLE users ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;

-- Backfill existing hardcoded user preferences
UPDATE users SET 
    email_font = CASE id
        WHEN 2 THEN 'Arial, sans-serif'
        WHEN 3 THEN 'sans-serif'
        WHEN 4 THEN 'sans-serif'
        WHEN 5 THEN 'sans-serif'
        ELSE 'sans-serif'
    END,
    email_font_size = CASE id
        WHEN 2 THEN '18px'
        WHEN 3 THEN '14px'
        WHEN 4 THEN '15px'
        WHEN 5 THEN '13px'
        ELSE '15px'
    END
WHERE email_font IS NULL OR email_font_size IS NULL;