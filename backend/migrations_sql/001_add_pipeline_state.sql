-- Migration 001: Add pipeline_state column to leads_raw
-- Replaces 7 scattered state columns with single explicit state machine

ALTER TABLE leads_raw ADD COLUMN IF NOT EXISTS pipeline_state VARCHAR(30) DEFAULT 'NEW';

-- Backfill pipeline_state from existing columns
UPDATE leads_raw SET pipeline_state = 
    CASE 
        WHEN is_unsubscribed THEN 'UNSUBSCRIBED'
        WHEN email_opt_in = FALSE THEN 'UNSUBSCRIBED'
        WHEN email_status = 'BOUNCED' THEN 'BOUNCED'
        WHEN is_responded = TRUE OR replied_at IS NOT NULL OR reply_intent IS NOT NULL THEN
            CASE 
                WHEN reply_intent IN ('INTERESTED', 'MEETING_REQUESTED', 'MEETING_SCHEDULED') THEN 'MEETING_REQUIRED'
                WHEN reply_intent = 'NOT_INTERESTED' THEN 'CLOSED_LOST'
                ELSE 'REPLIED'
            END
        WHEN followup_status = 'ACTIVE' THEN 'FOLLOWUP_ACTIVE'
        WHEN followup_status IN ('SCHEDULED', 'PENDING_APPROVAL', 'APPROVED') THEN 'FOLLOWUP_ACTIVE'
        WHEN followup_status = 'STOPPED' THEN 'CLOSED_LOST'
        WHEN followup_status = 'COMPLETED' THEN 'CLOSED_LOST'
        WHEN email_status = 'SENT' THEN 'SENT'
        WHEN email_status = 'SCHEDULED' THEN 'SCHEDULED'
        WHEN email_status = 'PENDING_APPROVAL' THEN 'DRAFT_PENDING'
        WHEN email_status = 'APPROVED' THEN 'DRAFT_PENDING'
        WHEN email_draft IS NOT NULL THEN 'DRAFT_PENDING'
        ELSE 'NEW'
    END
WHERE pipeline_state = 'NEW' OR pipeline_state IS NULL;

-- Add index for pipeline state queries
CREATE INDEX IF NOT EXISTS idx_leads_pipeline_state ON leads_raw(pipeline_state);

-- Add index for user + pipeline state (common query pattern)
CREATE INDEX IF NOT EXISTS idx_leads_user_pipeline ON leads_raw(user_id, pipeline_state);