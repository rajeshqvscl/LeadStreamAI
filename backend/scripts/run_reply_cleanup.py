"""
Manually trigger the daily reply-monitoring job (normally runs at 10:00 & 16:00 IST).

This job:
  1. Stops & deletes remaining generated follow-ups for every replied lead
     (followup_draft, pending/scheduled states) and moves the lead to "replied"
  2. Sends the admin email report
  3. Creates the in-app reminder notification

Usage:
  python scripts/run_reply_cleanup.py            # full run (cleanup + report + notification)
  python scripts/run_reply_cleanup.py --dry-run  # read-only — just show what would be cleaned
"""
import sys
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env", "../../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.append(os.getcwd())

from app.services.reply_cleanup_service import run_daily_reply_cleanup_and_report

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    mode = "DRY-RUN (read-only)" if dry_run else "FULL RUN"
    print("=" * 100)
    print(f"REPLY MONITOR JOB — {mode}")
    print("=" * 100)

    result = run_daily_reply_cleanup_and_report(
        dry_run=dry_run,
        send_email=not dry_run,
        create_reminder=not dry_run,
    )

    stats = result["cleanup_stats"]
    print(f"\nRun label          : {result['run_label']}")
    print(f"Replied leads found: {stats['replied_found']}")
    print(f"Followups deleted  : {stats['followups_deleted']}")
    print(f"Moved to replied   : {stats['moved_to_replied']}")
    print(f"Errors             : {stats['errors']}")
    print(f"New replies (report): {result['reply_count']}")
    print(f"Report emails sent : {result['email_sent']}")
    print(f"Notifications      : {result['notifications_created']}")

    if result["replies"]:
        print("\nReplies in this report:")
        for r in result["replies"]:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r.get('email')
            print(f"  - {name} | {r.get('company_name') or '-'} | intent={r.get('reply_intent') or '-'} | at={r.get('created_at')}")
    print("\nDone.")
