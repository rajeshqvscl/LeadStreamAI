#!/bin/bash
# =============================================================================
# LeadStream — Database Restore (into a TARGET database)
#
# Usage:
#   ./scripts/restore.sh <dump_file> <TARGET_DATABASE_URL>
#
# Restores a dump created by backup.sh into the TARGET database (typically a
# scratch/drill database — NEVER production without explicit intent).
#
# Safety: refuses to restore when TARGET equals the configured production
#         DATABASE_URL unless FORCE=1 is set AND you confirm the target URL.
#
# See project-brain/DR.md for the full runbook and restore-drill checklist.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/app/.env"

DUMP="${1:-}"
TARGET="${2:-}"

if [ -z "$DUMP" ] || [ -z "$TARGET" ]; then
  echo "Usage: ./scripts/restore.sh <dump_file> <TARGET_DATABASE_URL>"
  exit 1
fi
if [ ! -f "$DUMP" ]; then
  echo "ERROR: dump file not found: $DUMP"
  exit 1
fi
if ! command -v pg_restore >/dev/null 2>&1; then
  echo "ERROR: pg_restore not found on PATH (install PostgreSQL client tools)"
  exit 1
fi

# --- Resolve production DATABASE_URL for the safety comparison ---
PROD_URL=""
if [ -n "${DATABASE_URL:-}" ]; then
  PROD_URL="$DATABASE_URL"
elif [ -f "$ENV_FILE" ]; then
  PROD_URL="$(
    cd "$BACKEND_DIR" && python -c "
from dotenv import load_dotenv
import os
load_dotenv('app/.env')
print(os.getenv('DATABASE_URL', '') or '')
" 2>/dev/null || true
  )"
fi

if [ -n "$PROD_URL" ] && [ "$TARGET" = "$PROD_URL" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "❌ REFUSING: TARGET matches the configured production DATABASE_URL."
  echo "   If this is a deliberate production restore, re-run with FORCE=1"
  echo "   after double-checking the target. Restoring is DESTRUCTIVE."
  exit 1
fi

echo "Restoring $DUMP"
echo "  → target: ${TARGET%%@*}@<redacted-host>/<redacted-db>"   # never print credentials
echo "  (--clean: existing objects in target will be dropped)"
read -p "Proceed? (type 'restore' to confirm): " CONFIRM
if [ "$CONFIRM" != "restore" ]; then
  echo "Aborted."
  exit 1
fi

pg_restore \
  --no-owner --no-privileges \
  --clean --if-exists \
  --dbname="$TARGET" \
  "$DUMP"

echo ""
echo "✅ Restore complete into target database."
