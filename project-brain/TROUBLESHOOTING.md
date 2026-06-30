# Troubleshooting Guide

## Common Issues & Debug Steps

### 1. Follow-ups not sending

**Check the scheduler loop**: Look at `main.py:30-43`. The loop runs every 10s.

**Check the follow-up engine logs** (`followup_service.py:374-715`):
```
Error in process_outreach_sequences: ...
Lead X: followup_status is '...' — skipping
Lead X: already responded — skipping
Lead X: reply_intent is '...' — skipping
Outside hours — ...
Auto-pilot checking user X (...): auto_followup=..., has_token=...
```

**Common causes**:
| Cause | Check |
|-------|-------|
| Outside working hours | Only runs Mon-Fri 10AM-5PM IST (`_is_working_hours()`) |
| User auto_followup disabled | `SELECT auto_followup FROM users WHERE id = X` |
| User has no Gmail token | `SELECT google_refresh_token FROM users WHERE id = X` |
| Lead not in ACTIVE state | `SELECT followup_status FROM leads_raw WHERE id = X` |
| Lead already responded | `SELECT is_responded, reply_intent FROM leads_raw WHERE id = X` |
| Stage already completed | `SELECT followup_stage FROM leads_raw WHERE id = X` |

### 2. Replies not being detected

**Check polling logs** (`gmail.py:1205-1359`):
```
DEBUG: Skipping X — not a lead we contacted through this platform.
DEBUG: Cross-account reply — retargeted to user X
SUCCESS: Auto-detected reply from X. Intent: INTERESTED
```

**Check push notification logs** (`gmail.py:100-157`):
```
DEBUG: Received Gmail push for X with historyId Y
```

**Common causes**:
| Cause | Check |
|-------|-------|
| Lead email status isn't SENT/REPLIED/CLOSED | `SELECT email_status FROM leads_raw WHERE email = X` |
| Lead is_responded already TRUE | `SELECT is_responded FROM leads_raw WHERE email = X` |
| Gmail API scope issue | Check `auth.py` logs: "linked account without read scope" |
| Poll dedup skipping | Message already in `gmail_processed_messages` |
| Sender is the user themselves | The `SENDER CHECK` skips if `user.email` matches `sender_email` |

### 3. Cross-account stop not working

**Check the logs** (`gmail.py:499-524` + current cross-account code):
```
Stopped followup for X (email@domain.com) under user Y — same email replied on another account
```

**Check the code path used**:
- **Push path** (`process_gmail_history` → `handle_potential_reply`): Uses single `user_id`. The cross-account fallback in `handle_potential_reply` kicks in when lead not found under the push recipient.
- **Poll path** (`poll_all_users_for_replies` → `handle_potential_reply`): Already searches across all users. The cross-account stop in the same-email/domain queries handles the rest.

### 4. Emails bouncing

**Check bounce logs** (`gmail.py:1306-1341`):
```
Marked lead X (email@domain.com) as BOUNCED. Reason: Email doesn't exist
```

**Bounce reasons mapped**:
- `5.1.1` / `does not exist` → Email doesn't exist
- `5.2.2` / `over quota` → Inbox full
- `5.7.1` / `spam` / `blocked` → Blocked by spam filter
- `5.4.1` / `no mx` → Domain doesn't exist
- `4.x.x` / `temporary` → Temporary issue (will retry)

### 5. Gmail API errors

**Common Gmail errors**:
| Error | Cause | Fix |
|-------|-------|-----|
| `invalid_scope` | OAuth scope mismatch | User needs to re-authenticate |
| `Metadata scope does not support 'q' parameter` | Restricted OAuth scope | Falls back to simple list (no filter) |
| `Request entity too large` | Attachment too big | Reduce attachment size |
| 401 Unauthorized | Token expired/revoked | Check `google_refresh_token` in users table |

### 6. Cross-account domain stop not working (personal domains)

The code skips personal email domains (gmail.com, yahoo.com, etc.) for domain-level stopping. Only exact email match is stopped for these domains. Check `personal_domains` set in `gmail.py`:

```python
personal_domains = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', ...}
```

### 7. Manually inspect lead state

Run these queries to understand a lead's current state:

```sql
SELECT id, email, email_status, followup_status, followup_stage,
       is_responded, reply_intent, rejection_reason,
       last_outreach_at, user_id
FROM leads_raw
WHERE email = 'person@example.com';
```

### 8. Manually stop follow-ups for a lead

```sql
UPDATE leads_raw
SET followup_status = 'STOPPED', is_responded = TRUE, updated_at = NOW()
WHERE LOWER(email) = LOWER('person@example.com');
```

### Key Log Points in Code

| What | File:Line | Log Prefix |
|------|-----------|------------|
| Scheduler loop | `main.py:42` | `Scheduler error:` |
| Polling start | `gmail.py:1205` | (function entry) |
| Reply detected | `gmail.py:466` | `SUCCESS: Auto-detected reply` |
| Reply skipped (not our lead) | `gmail.py:302` | `DEBUG: Skipping X — not a lead` |
| Cross-account retarget | `gmail.py:301` | `DEBUG: Cross-account reply — retargeted` |
| Cross-account email stopped | `gmail.py:521` | `Stopped followup for X under user Y` |
| Cross-account domain stopped | `gmail.py:494` | `Stopped followup for X — same company` |
| Bounce detected | `gmail.py:1341` | `Marked lead X as BOUNCED` |
| Follow-up engine start | `followup_service.py:427` | `Auto-pilot checking user X` |
| Follow-up sending | `followup_service.py:703` | `Auto-followup sent from X to Y` |
| Follow-up skipped | `followup_service.py:528-543` | Various skip reasons |
| Working hours check | `followup_service.py:385` | `Outreach paused: Weekend/hours` |
| Push notification | `gmail.py:126` | `DEBUG: Received Gmail push for X` |
