# Reply Detection

**Files**: `backend/app/api/gmail.py`
**Two paths**: Push notifications (real-time) + Polling (every 10s, reliable fallback)

## Flow Diagram

```mermaid
graph TD
    subgraph "Push Path (Pub/Sub)"
        PUSH[Google sends Pub/Sub push] --> FIND_USER[Find user by emailAddress]
        FIND_USER --> HIST[process_gmail_history]
        HIST --> LABEL{Has INBOX label?<br/>Not SENT?}
        LABEL -->|Yes| DEDUP{Already in<br/>gmail_processed_messages?}
        DEDUP -->|No| HPR[handle_potential_reply]
        DEDUP -->|Yes| SKIP1[Skip - already processed]
        LABEL -->|No| SKIP2[Skip - sent or other]
    end

    subgraph "Poll Path (every 10s)"
        POLL[poll_all_users_for_replies] --> ITER[Loop through all users]
        ITER --> GMAIL[Query Gmail: label:INBOX -from:me]
        GMAIL --> DEDUP2{Already in<br/>gmail_processed_messages?}
        DEDUP2 -->|No| BOUNCE{Is it a bounce?<br/>mailer-daemon,<br/>Undeliverable?}
        BOUNCE -->|Yes| HANBOUNCE[Handle bounce: mark lead as BOUNCED]
        BOUNCE -->|No| FINDLEAD{Find lead by email<br/>(any user, is_responded=FALSE)}
        FINDLEAD -->|Found| HPR[handle_potential_reply]
        FINDLEAD -->|Not found| SKIP3[Skip - not our lead]
    end

    subgraph "Handler"
        HPR --> SELF{Is sender the<br/>user themselves?}
        SELF -->|Yes| SKIP4[Skip]
        SELF -->|No| AI[AI classify reply intent]
        AI --> UPDATE[Update lead + stop follow-ups]
        UPDATE --> EMAIL_STOP[Stop same email<br/>across all accounts]
        EMAIL_STOP --> DOMAIN_STOP[Stop same domain<br/>across all accounts<br/>(non-personal domains)]
        DOMAIN_STOP --> COMPANY_STOP[Stop same company<br/>across all users]
        COMPANY_STOP --> REMINDER[Create reminder if<br/>MEETING_REQUESTED]
    end
```

## Push Path Details

**Entry**: `POST /api/gmail/pubsub-push` (`gmail.py:100-157`)

1. Google Cloud Pub/Sub sends notification with `emailAddress` + `historyId`
2. Find the local user whose email matches
3. `process_gmail_history(user_id, last_history_id)` fetches all changes since last history ID
4. For each new message: checks labels (`INBOX` present, `SENT` absent)
5. Checks `gmail_processed_messages` dedup table
6. Calls `handle_potential_reply(user_id, thread_id, full_msg)`

**Known gap**: If the response is for a lead owned by a DIFFERENT user, the initial lookup by the push recipient's `user_id` won't find it. The fallback kicks in inside `handle_potential_reply` (cross-account retarget).

## Poll Path Details

**Entry**: `poll_all_users_for_replies()` (`gmail.py:1205-1359`)

1. Get all users with `google_refresh_token IS NOT NULL`
2. For each user: query Gmail `label:INBOX -from:me` (latest 50 messages)
3. Check `gmail_processed_messages` dedup
4. Check for bounces (mailer-daemon, postmaster, "Undeliverable" subject)
5. Find lead by email across ALL users (no user_id filter):
   ```sql
   SELECT id, user_id FROM leads_raw
   WHERE LOWER(email) = LOWER(%s) AND is_responded = FALSE
   LIMIT 1
   ```
6. Call `handle_potential_reply(target_uid, thread_id, full_msg)` where `target_uid` is the lead's owner

## handle_potential_reply — Core Handler

**Function**: `handle_potential_reply(user_id, thread_id, message_data)` (`gmail.py:203-623`)

### Steps

1. **Extract sender email** from message headers
2. **Clean message body** — strip HTML, quoted reply text ("On ... wrote:")
3. **Sender self-check** — skip if the message was sent by the user themselves
4. **Outreach-only filter** — only process if the email exists as a lead with status SENT/REPLIED/CLOSED/SCHEDULED
   - If not found under this user → cross-account fallback (search all users)
5. **AI classification** — `llm.classify_reply(body)` returns:
   - `intent`: MEETING_REQUESTED | INTERESTED | NEEDS_MORE_INFO | NOT_INTERESTED
   - `deal_size`, `sentiment_score`, `urgency_level`, `rejection_reason`, etc.
6. **PDF attachment handling** — uploads pitch decks to Google Drive
7. **RAG processing** — sends to external RAG engine for analysis
8. **Update lead** — sets `is_responded=TRUE`, `email_status=REPLIED/CLOSED`, `reply_intent`, `followup_status='STOPPED'`
9. **Cross-account stop** — stops same email across ALL users
10. **Same-domain stop** — stops same domain across ALL users (except personal domains)
11. **Same-company stop** — stops same company leads
12. **Create reminder** — auto-creates a reminder if MEETING_REQUESTED

### Lead update query

```sql
UPDATE leads_raw
SET is_responded = TRUE,
    email_status = %s,           -- 'REPLIED' or 'CLOSED'
    reply_intent = %s,           -- classified intent
    check_size = COALESCE(%s, check_size),
    deal_size = %s,
    pitch_deck_url = %s,
    rag_advice = %s,
    rag_intelligence = %s,
    sector = COALESCE(%s, sector),
    sentiment_score = %s,
    urgency_level = %s,
    remarks = %s,
    rejection_reason = %s,
    updated_at = NOW(),
    followup_status = 'STOPPED'
WHERE LOWER(email) = LOWER(%s) AND user_id = %s
RETURNING id, first_name, last_name, user_id
```

### Cross-account same-email stop

```sql
SELECT id, first_name, last_name, email, user_id FROM leads_raw
WHERE LOWER(email) = LOWER(%s) AND id != %s
AND followup_status = 'ACTIVE' AND is_responded = FALSE
```
Then for each: `UPDATE SET is_responded=TRUE, email_status=..., reply_intent=..., followup_status='STOPPED'`

### Cross-account same-domain stop

```sql
SELECT id, first_name, last_name, email FROM leads_raw
WHERE id != %s
AND followup_status = 'ACTIVE' AND is_responded = FALSE
AND LOWER(split_part(email, '@', 2)) = %s
```
Skips personal domains (gmail.com, yahoo.com, etc.) — only exact email match for those.
