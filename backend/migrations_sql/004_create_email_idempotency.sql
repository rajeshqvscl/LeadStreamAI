-- Migration 004: Create email_idempotency table
-- Prevents duplicate email sends via idempotency keys

CREATE TABLE IF NOT EXISTS email_idempotency (
    key VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_idempotency_expires ON email_idempotency(expires_at);

-- Function to clean expired idempotency keys (can be called via cron)
CREATE OR REPLACE FUNCTION cleanup_expired_idempotency_keys()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM email_idempotency WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;