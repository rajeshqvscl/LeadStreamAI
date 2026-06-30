# Database Schema

> PostgreSQL on Neon. All table creation and migrations happen in `backend/app/database.py`.

## leads_raw — Core lead table

```sql
CREATE TABLE leads_raw (
    id              SERIAL PRIMARY KEY,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT UNIQUE,          -- originally unique; now composite (email, user_id)
    domain          TEXT,
    linkedin_url    TEXT,
    company_name    TEXT,
    persona         TEXT,
    phone           TEXT,
    city            TEXT,
    country         TEXT,
    source          TEXT,
    raw_payload     JSONB,
    fit_score       INTEGER DEFAULT 0,
    validation_status TEXT DEFAULT 'PENDING',
    email_status    TEXT DEFAULT 'PENDING',  -- PENDING, SCHEDULED, SENT, REPLIED, CLOSED, BOUNCED
    email_draft     TEXT,
    family_office_name TEXT,
    labels          TEXT[] DEFAULT '{}',
    user_id         INTEGER,
    user_name       TEXT,
    is_unsubscribed BOOLEAN DEFAULT FALSE,
    manual_entry    BOOLEAN DEFAULT FALSE,
    is_responded    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    scheduled_at    TIMESTAMP,
    -- Follow-up sequence columns
    followup_stage      INTEGER DEFAULT 0,     -- 0=just sent, 1/2/3=follow-up number
    followup_status     TEXT DEFAULT 'IDLE',   -- IDLE, ACTIVE, COMPLETED, STOPPED
    followup_draft      TEXT,                  -- custom follow-up body
    followup_approved   BOOLEAN DEFAULT FALSE,
    gmail_thread_id     TEXT,                  -- Gmail thread for threading
    gmail_message_id    TEXT,                  -- RFC Message-ID
    first_outreach_at   TIMESTAMP,
    first_outreach_subject TEXT,
    last_outreach_at    TIMESTAMP,
    last_outreach_subject TEXT,
    cc_email            TEXT,
    gmail_draft_id      TEXT,
    draft_template_used TEXT,
    tracking_token      TEXT,
    -- Reply tracking
    reply_intent        TEXT,    -- INTERESTED, MEETING_REQUESTED, NEEDS_MORE_INFO, NOT_INTERESTED
    rejection_reason    TEXT,
    remarks             TEXT,
    sentiment_score     INTEGER,
    urgency_level       TEXT,
    -- Deal tracking
    deal_size           TEXT,
    check_size          TEXT,
    pitch_deck_url      TEXT,
    meeting_link        TEXT,
    meeting_time        TIMESTAMP,
    -- RAG
    rag_advice          TEXT,
    rag_intelligence    TEXT,    -- JSONB stored as TEXT
    sector              TEXT,
    designation         TEXT,
    industry            TEXT,
    lead_type           TEXT
);
```

### Key indexes

```sql
-- Composite unique: one lead per email per user
CREATE UNIQUE INDEX leads_raw_email_user_unique ON leads_raw (email, COALESCE(user_id, -1));
CREATE INDEX idx_leads_raw_email_status ON leads_raw (email_status);
CREATE INDEX idx_leads_raw_email_status_user ON leads_raw (email_status, user_id);
CREATE INDEX idx_leads_raw_user_id ON leads_raw (user_id);
CREATE INDEX idx_leads_raw_updated_at ON leads_raw (updated_at DESC);
CREATE INDEX idx_leads_raw_last_outreach ON leads_raw (last_outreach_at DESC);
CREATE INDEX idx_leads_raw_followup_status ON leads_raw (followup_status);
CREATE INDEX idx_leads_raw_email_draft ON leads_raw (email_draft) WHERE email_draft IS NOT NULL;
CREATE INDEX idx_leads_raw_lower_email ON leads_raw (LOWER(email));  -- for cross-account lookups
```

### email_status state machine

```
PENDING → SCHEDULED → SENT → REPLIED
                            → CLOSED  (NOT_INTERESTED)
                            → BOUNCED
         SCHEDULED → SENT  (when scheduled_at <= NOW())
```

### followup_status state machine

```
IDLE → ACTIVE → COMPLETED  (stage >= 3)
             → STOPPED     (reply received, user stopped, or bounced)
```

### Key SQL queries used in code

**Find reply lead** (`gmail.py`):
```sql
SELECT id, user_id FROM leads_raw
WHERE LOWER(email) = LOWER(%s) AND user_id = %s
AND email_status IN ('SENT', 'REPLIED', 'CLOSED', 'SCHEDULED')
```

**Cross-account fallback** (`gmail.py`):
```sql
SELECT id, user_id FROM leads_raw
WHERE LOWER(email) = LOWER(%s)
AND email_status IN ('SENT', 'REPLIED', 'CLOSED', 'SCHEDULED')
AND is_responded = FALSE LIMIT 1
```

**Pick leads for follow-up** (`followup_service.py`):
```sql
SELECT DISTINCT ON (LOWER(l.email)) l.*, u.id as sender_id, u.email as sender_email, ...
FROM leads_raw l
JOIN users u ON l.user_id = u.id
WHERE l.followup_status = 'ACTIVE'
AND l.email_status = 'SENT'
AND COALESCE(l.is_responded, FALSE) = FALSE
AND COALESCE(l.reply_intent, '') NOT IN ('INTERESTED', 'MEETING_SCHEDULED', 'NOT_INTERESTED')
AND COALESCE(l.email_status, '') NOT IN ('REPLIED', 'INTERESTED', 'MEETING SCHEDULED', 'NOT_INTERESTED', 'BOUNCED')
AND l.followup_stage < 3
ORDER BY LOWER(l.email), l.last_outreach_at ASC
```

**Cross-account domain stop** (`gmail.py`):
```sql
SELECT id, first_name, last_name, email FROM leads_raw
WHERE id != %s
AND followup_status = 'ACTIVE' AND is_responded = FALSE
AND LOWER(split_part(email, '@', 2)) = %s
```

## users — User/account table

```sql
CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    username            TEXT UNIQUE NOT NULL,
    email               TEXT UNIQUE NOT NULL,
    full_name           TEXT,
    password_hash       TEXT,
    role                TEXT DEFAULT 'USER',        -- USER, ADMIN
    is_active           BOOLEAN DEFAULT TRUE,
    is_approved         BOOLEAN DEFAULT FALSE,
    has_db_access       BOOLEAN DEFAULT FALSE,
    google_id           TEXT,
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_token_expiry TIMESTAMP,
    credits_used        INTEGER DEFAULT 0,
    credits_limit       INTEGER DEFAULT 200,
    auto_followup       BOOLEAN DEFAULT FALSE,     -- per-user auto-followup toggle
    outreach_daily_limit INTEGER DEFAULT 200,
    team                TEXT DEFAULT 'CLIENT',
    created_at          TIMESTAMP DEFAULT NOW()
);
```

## activity_log — Audit trail

```sql
CREATE TABLE activity_log (
    id              SERIAL PRIMARY KEY,
    lead_id         INTEGER,
    action          TEXT NOT NULL,       -- EMAIL_SENT, AUTO_FOLLOWUP_SENT, FOLLOWUP_STOPPED,
                                        -- BOUNCED, OPENED, CLICKED, DRAFT_GENERATED, etc.
    details         TEXT,
    performed_by    TEXT DEFAULT 'system',
    user_id         INTEGER,
    user_name       TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
-- Indexes: (action, user_id, created_at DESC), (lead_id), (created_at DESC)
```

## gmail_processed_messages — Dedup table

```sql
CREATE TABLE gmail_processed_messages (
    message_id  TEXT PRIMARY KEY,
    user_id     INTEGER,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

Prevents the same Gmail message from being processed twice across polling cycles.

## Other tables

| Table | Purpose |
|-------|---------|
| `campaigns` | Campaign definitions (tone, target industry, templates) |
| `recipients` | Campaign-to-lead mapping with unique tracking tokens |
| `campaign_events` | Open/click/unsubscribe event logs |
| `prompts` | Configurable AI prompt templates (classification, email gen, follow-ups) |
| `reminders` | User task reminders with priority |
| `family_offices` | Investor family office directory |
| `company_registry` | Dynamic JSONB sheet data for company database |
| `unsubscribe_list` | Global email opt-out list |
