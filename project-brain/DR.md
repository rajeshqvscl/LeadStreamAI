# LeadStream — Disaster Recovery Runbook

> **Status: 🟡 Scripts written (3 Sep 2026) — restore drill NOT yet performed.**
> Do not treat DR as production-ready until the drill in §4 passes on a scratch database.

## 1. Recovery layers

| Layer | What | Owns |
|---|---|---|
| **1 — Neon PITR (primary)** | Neon's managed point-in-time recovery + continuous WAL archiving (configure retention in the Neon console). Recovers the database to any point within the retention window. | Neon platform |
| **2 — Logical dump (independent copy)** | `backend/scripts/backup.sh` → timestamped `pg_dump` custom-format file. Restorable into any PostgreSQL, even outside Neon. | Backend admin (this runbook) |
| **3 — Code rollback** | `backend/scripts/rollback.sh` — git-based code rollback (separate from data recovery). | Backend admin |

## 2. RPO / RTO targets (proposed — confirm once the drill passes)

| Metric | Target | Basis |
|---|---|---|
| **RPO (data loss)** | ≤ 24 h on the logical dump; **minutes on Neon PITR** (platform WAL) | Nightly `backup.sh` + Neon PITR retention |
| **RTO (recovery time)** | ≤ 1 h from a logical dump; ≤ 30 min from Neon PITR | pg_restore of ~1 GB scale DB + smoke checks |
| **Backup retention** | 14 nightly dumps (auto-pruned) + Neon PITR window (set in Neon console, e.g. 7 days) | `backup.sh` |
| **Restore owner** | Backend admin / on-call — only person allowed to run `restore.sh` or touch Neon PITR | — |
| **Drill frequency** | Quarterly (after every schema-migration release until stable) | — |

> These are **proposed targets**, not verified numbers. The first drill (§4) should
> measure actual restore wall-clock time and that becomes the real RTO baseline.

## 3. Operational runbook

### 3.1 Nightly backup (should be scheduled)

```bash
cd backend
./scripts/backup.sh                 # writes backend/backups/leadstream_<ts>.dump
```

- Produces a custom-format dump; auto-prunes to the 14 newest.
- **Recommended**: run nightly via Render cron or a scheduler, and copy dumps off Render
  (e.g. an S3/R2 bucket) so a Render account issue can't lose both copies.

### 3.2 Emergency restore to production (rare — destructive)

```bash
cd backend
# 1. Stop senders first: pause the worker + scheduler (or set
#    SCHEDULER_FOLLOWUP_INTERVAL_SEC very high) so no email fires mid-restore.
# 2. Pick the dump:
ls -1t backups/leadstream_*.dump
# 3. Restore (this DROPS existing objects in production):
FORCE=1 ./scripts/restore.sh backups/leadstream_<latest>.dump "$DATABASE_URL"
# 4. Verify (§5), then restart workers/schedulers.
```

> Alternative to step 3: Neon PITR restore from the console (choose the target
> timestamp), then point `DATABASE_URL` at the restored branch.

## 4. Restore drill (must run on a SCRATCH database — never production)

```bash
cd backend

# 1. Create a scratch database (Neon console → new branch/project, or locally):
#    e.g. postgresql://user:pass@host/leadstream_drill

# 2. Take a fresh backup of production data:
./scripts/backup.sh

# 3. Restore the newest dump into the scratch DB:
./scripts/restore.sh backups/leadstream_<latest>.dump "postgresql://.../leadstream_drill"
#    → confirm with: restore

# 4. Verify the restore (§5).

# 5. Tear down the scratch database so real data never lingers outside prod.
```

## 5. Verification checklist (run after ANY restore)

| # | Check | Query / command | Pass |
|---|---|---|---|
| 1 | Table row counts sane | `SELECT count(*) FROM leads_raw;` etc. → matches pre-backup counts | ☐ |
| 2 | FKs / joins intact | spot-check a lead's activity_log rows resolve to the lead | ☐ |
| 3 | Latest data present | `SELECT max(created_at), max(updated_at) FROM leads_raw;` → close to backup time | ☐ |
| 4 | **Encrypted OAuth intact** | `SELECT count(*) FROM users WHERE google_refresh_token IS NOT NULL;` AND sampled values start with the Fernet prefix (`gAAAA`) and do **not** contain `@` / plaintext fragments | ☐ |
| 5 | Unique constraints re-applied | `INSERT` of a duplicate `(email, user_id)` fails (or check `\d leads_raw` constraints) | ☐ |
| 6 | `sessions` valid | `SELECT count(*) FROM sessions WHERE expires_at > NOW();` → > 0 so users can log in | ☐ |
| 7 | Sequences advanced | `SELECT last_value FROM leads_raw_id_seq;` ≥ max(id) (new inserts must not collide) | ☐ |
| 8 | App boots against restored DB | `python scripts/smoke_test.py` and `/api/health/ready` → ready | ☐ |
| 9 | Queue empty/stale-safe | Restored `email_idempotency` must cover sent leads — verify a sample lead's `gmail_message_id` is set where activity says EMAIL_SENT | ☐ |
| 10 | Restore wall-clock measured | `time ./scripts/restore.sh ...` → recorded as the real RTO baseline | ☐ |

## 6. Post-restore hygiene

- Delete the scratch/drill database immediately after the drill.
- Confirm no **new** sends happened against the restored data before senders were paused
  (check `activity_log` max(created_at) for EMAIL_SENT/AUTO_FOLLOWUP_SENT around the restore window).
- If the restore was a production emergency: verify Google OAuth still works on one real
  account (refresh tokens are encrypted with the same `TOKEN_ENCRYPTION_KEY` — if that key
  changed, tokens will not decrypt and Gmail connections must be re-authorized).
