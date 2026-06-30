# LeadStreamAI — Project Brain

This folder documents the full system architecture, logic flows, database schema, and troubleshooting guides. Use it to understand how the system works before making changes or debugging issues.

## How to use

1. **New issue or feature?** Start with `ARCHITECTURE.md` for high-level context, then drill into the specific flow in `FLOWS/`
2. **Database question?** Check `DATABASE.md` — lists all tables, columns, constraints, and key queries
3. **Which file does what?** See `FILE-MAP.md`
4. **5 accounts setup?** See `ACCOUNTS.md`
5. **Debugging?** See `TROUBLESHOOTING.md`

## Contents

| File | What it covers |
|------|---------------|
| `ARCHITECTURE.md` | High-level system diagram, tech stack, deployment |
| `FILE-MAP.md` | Every file in backend/ and frontend/ with description |
| `DATABASE.md` | All tables, columns, constraints, indexes, key queries |
| `ACCOUNTS.md` | The 5 sender accounts (users), templates, personas |
| `TROUBLESHOOTING.md` | Common problems, debug steps, log points |
| `FLOWS/00-scheduler-loop.md` | The 10s background loop |
| `FLOWS/01-reply-detection.md` | Push + Poll → handle_potential_reply → cross-account stop |
| `FLOWS/02-followup-engine.md` | process_outreach_sequences → filtering → sending |
| `FLOWS/03-email-dispatch.md` | send_email → Gmail API / SMTP / Resend routing |
| `FLOWS/04-lead-lifecycle.md` | Lead status transitions with triggers |
| `FLOWS/05-auth-oauth.md` | Authentication and Google OAuth flow |
| `FLOWS/06-draft-generation.md` | AI draft generation → approval → sending flow |
