# Follow-up Engine

**File**: `backend/app/services/followup_service.py`
**Function**: `process_outreach_sequences()` (line 374-715)
**Run by**: Scheduler loop every 10s

## Flow Diagram

```mermaid
graph TD
    START[process_outreach_sequences] --> HOURS{Working hours?<br/>Mon-Fri 10AM-5PM IST?}
    HOURS -->|No| EXIT1[Exit - outside hours]
    HOURS -->|Yes| QUERY[Query leads due for follow-ups]
    
    QUERY --> FILTERS{Check all conditions}
    FILTERS --> F1[followup_status = 'ACTIVE']
    FILTERS --> F2[email_status = 'SENT']
    FILTERS --> F3[is_responded = FALSE]
    FILTERS --> F4[reply_intent not INTERESTED/MEETING_SCHEDULED/NOT_INTERESTED]
    FILTERS --> F5[email_status not REPLIED/INTERESTED/NOT_INTERESTED/BOUNCED]
    FILTERS --> F6[followup_stage < 3]
    FILTERS --> PASS[IN: leads pass all filters]
    
    PASS --> GROUP[Group by sender user]
    
    GROUP --> USER_LOOP[For each user group]
    USER_LOOP --> ENABLED{User auto_followup enabled?<br/>Has google_refresh_token?}
    ENABLED -->|No| SKIP_USER[Skip this user]
    ENABLED -->|Yes| LEAD_LOOP[For each lead in group]
    
    LEAD_LOOP --> HOURS2{Re-check working hours}
    HOURS2 -->|Outside| BREAK[Break - stop batch]
    HOURS2 -->|OK| CHECK_RIPE{Stage timing met?<br/>Stage 0 ≥ 2 days<br/>Stage 1 ≥ 5 days<br/>Stage 2 ≥ 8 days}
    CHECK_RIPE -->|No| NEXT_LEAD[Skip - not due yet]
    CHECK_RIPE -->|Yes| DEFENCE{Is Defence lead?<br/>(keyword check)}
    DEFENCE -->|Yes| SKIP_DEF[Skip]
    DEFENCE -->|No| REVERIFY[Re-verify state from DB<br/>(race condition guard)]
    
    REVERIFY --> STILL_OK{Still ACTIVE?<br/>Still unresponded?<br/>Still same stage?<br/>Auto_followup still on?}
    STILL_OK -->|No| SKIP_CHANGED[Skip]
    STILL_OK -->|Yes| THREAD{Has gmail_thread_id?}
    THREAD -->|No| HEAL[Attempt to heal thread ID<br/>by searching Gmail Sent]
    HEAL --> STILL_THREAD{Found thread?}
    STILL_THREAD -->|No| SKIP_THREAD[Skip - no thread<br/>(imported/ghost lead)]
    
    THREAD -->|Yes| DUP_CHECK{Already sent this stage?<br/>(activity_log check)}
    DUP_CHECK -->|Already sent| SKIP_DUP[Skip duplicate]
    DUP_CHECK -->|No| CLAIM[Atomic claim: UPDATE ...<br/>WHERE followup_stage = old]
    CLAIM --> CLAIMED{rowcount > 0?<br/>(only one worker wins)}
    CLAIMED -->|No| SKIP_CLAIM[Another worker claimed it]
    CLAIMED -->|Yes| SEND[Send follow-up email]
    SEND --> LOG[Log success + sleep 5s]
    LOG --> LEAD_LOOP
```

## SQL Query to Pick Leads

```sql
SELECT DISTINCT ON (LOWER(l.email)) l.*,
       u.id as sender_id,
       u.email as sender_email,
       u.full_name as sender_name,
       u.auto_followup,
       u.outreach_daily_limit,
       u.google_refresh_token
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

## Timing Schedule

| Current Stage | Next Follow-up | Days Since Last Outreach |
|---------------|----------------|--------------------------|
| 0 (initial) | Stage 1 | ≥ 2 days |
| 1 | Stage 2 | ≥ 5 days |
| 2 | Stage 3 | ≥ 8 days |
| ≥ 3 | COMPLETED | N/A |

## Template Selection

**Function**: `get_template_followup(lead, next_stage)` (`followup_service.py:149-266`)

1. **Custom template** — checks if the lead's prompt template has `followup_1/2/3` columns filled
2. **Known persona override** — checks `draft_template_used` for known names (Yashika, Palak, Kajal, etc.)
3. **Dynamic detection** — falls back to detecting by subject/draft/persona/sector keywords
4. **Default templates** — 10 predefined template sets in `FOLLOWUP_TEMPLATES` dict

## Subject Line

Follow-ups use: `Re: {original_subject}`

## Pre-send Verification

Before sending, the code re-fetches the lead's state from DB to guard against race conditions:

```python
SELECT l.followup_stage, l.followup_status, l.is_responded,
       l.reply_intent, l.email_status, u.auto_followup
FROM leads_raw l
JOIN users u ON l.user_id = u.id
WHERE l.id = %s
```

**Skip conditions** (after re-verify):
- `followup_stage` changed (another worker advanced it)
- `followup_status` is not 'ACTIVE'
- `is_responded` is TRUE
- `reply_intent` is INTERESTED/MEETING_SCHEDULED/NOT_INTERESTED
- `email_status` is REPLIED/INTERESTED/MEETING SCHEDULED/NOT_INTERESTED/BOUNCED
- `auto_followup` turned off

## Atomic Claim (Race Condition Guard)

```sql
UPDATE leads_raw
SET followup_stage = %s, followup_status = %s, updated_at = NOW()
WHERE id = %s AND followup_stage = %s AND followup_status = 'ACTIVE'
```

Only the first worker to execute this gets `rowcount=1` — others get 0 and skip. This prevents duplicate sends when multiple workers are running.

## Sender Profile

```python
profile = get_sender_profile(str(uid))
name = profile.get('full_name') or profile.get('username') or 'Team'
first_name = name.split()[0]
```

The sender's first name is used in the email signature: `Regards, {first_name}`.
