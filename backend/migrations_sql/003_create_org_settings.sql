-- Migration 003: Create org_settings table
-- Centralizes org-level configuration (CC emails, website, LinkedIn)

CREATE TABLE IF NOT EXISTS org_settings (
    id SERIAL PRIMARY KEY,
    default_cc TEXT DEFAULT 'lalit.h@qvscl.com',
    vismaya_cc TEXT DEFAULT 'rajesh.s@qvscl.com',
    website TEXT DEFAULT 'https://qvscl.com',
    linkedin_url TEXT DEFAULT 'https://linkedin.com/company/qvscl',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default org settings if table is empty
INSERT INTO org_settings (default_cc, vismaya_cc, website, linkedin_url)
SELECT 'lalit.h@qvscl.com', 'rajesh.s@qvscl.com', 'https://qvscl.com', 'https://linkedin.com/company/qvscl'
WHERE NOT EXISTS (SELECT 1 FROM org_settings);

-- Add trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_org_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_org_settings_updated ON org_settings;
CREATE TRIGGER trigger_org_settings_updated
    BEFORE UPDATE ON org_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_org_settings_timestamp();