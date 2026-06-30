# Accounts — The 5 Senders

The system has 5 user accounts (senders). Each has its own Gmail OAuth connection, sender identity, and draft template configuration.

## Account Overview

| # | Name | Email | Team | Templates/Personas Used |
|---|------|-------|------|------------------------|
| 1 | **Harsh Bisht** | harshbisht180@gmail.com | CLIENT | Default sender, also used as SMTP fallback |
| 2 | **Yashika** | (yashika's email) | INVESTOR | `yashika_draft_ai_tech`, `yashika_draft_agritech` |
| 3 | **Palak** | (palak's email) | INVESTOR | `palak_mam_corporate_advisory`, `palak_mam_mna_fundraising` |
| 4 | **Kajal** | (kajal's email) | INVESTOR | `kajal_mam_qvscl_intro`, `kajal_mam_health_ecosystem`, `kajal_mam_jv` |
| 5 | **Vismaya** | (vismaya's email) | INVESTOR | `vismaya_leadstream` |

## How sender identity is resolved

When an email is sent:
1. `leads_raw.user_id` points to the sender's `users.id`
2. `followup_service.py` joins `leads_raw` with `users`:
   ```sql
   SELECT u.email as sender_email, u.full_name as sender_name, ...
   ```
3. `email_service.py` uses these values in the Gmail API `send` call — the email appears to come FROM that user's Gmail

## Per-user configuration

Each user has independent settings in the `users` table:

| Column | Per-user? | Purpose |
|--------|-----------|---------|
| `auto_followup` | ✅ | Whether automated follow-ups run for this user |
| `outreach_daily_limit` | ✅ | Daily send cap (currently unused — set to 999999 in code) |
| `google_refresh_token` | ✅ | Gmail OAuth token (must be present for auto-followup) |
| `team` | ✅ | CLIENT or INVESTOR group |

## Cross-account behavior

- **Reply detection**: When any user receives a reply, the code searches ALL users for leads with that email
- **Follow-up stop**: Stops follow-ups for the same email AND same domain across ALL 5 accounts
- **Blacklisted domains** (`personal_domains` in code): gmail.com, yahoo.com, outlook.com, hotmail.com, etc. — these are NOT stopped at domain level (only exact email match)

## Sender profile resolution

In `followup_service.py`, the function `get_sender_profile(str(uid))` fetches the sender's name from the `users` table. Used in the email signature:
```python
profile = get_sender_profile(str(uid))
name = profile.get('full_name') or profile.get('username') or 'Team'
first_name = name.split()[0]
```
