#!/bin/bash
# =============================================================================
# LeadStream — Logical Database Backup (Neon / PostgreSQL)
#
# Usage:
#   ./scripts/backup.sh [output_dir]        # default: backend/backups/
#
# Produces a timestamped pg_dump (custom format) and keeps the 14 newest.
# Reads DATABASE_URL from the environment, falling back to backend/app/.env.
#
# NOTE: This is the off-platform logical copy. Neon's managed PITR (platform
#       level, configured in the Neon console) is the primary recovery layer;
#       this script gives an independently restorable copy. See
#       project-brain/DR.md for the full runbook and RPO/RTO definitions.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/app/.env"

# --- Resolve DATABASE_URL (never echo its value — it contains a password) ---
if [ -z "${DATABASE_URL:-}" ] && [ -f "$ENV_FILE" ]; then
  DATABASE_URL="$(
    cd "$BACKEND_DIR" && python -c "
from dotenv import load_dotenv
import os
load_dotenv('app/.env')
print(os.getenv('DATABASE_URL', '') or '')
" 2>/dev/null || true
  )"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL not set and could not be read from $ENV_FILE"
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump not found on PATH (install PostgreSQL client tools)"
  exit 1
fi

OUT_DIR="${1:-$BACKEND_DIR/backups}"
mkdir -p "$OUT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
DUMP="$OUT_DIR/leadstream_$STAMP.dump"

echo "Backing up database → $DUMP"
pg_dump "$DATABASE_URL" \
  --no-owner --no-privileges \
  --format=custom \
  --file="$DUMP"

echo ""
echo "✅ Backup written: $DUMP"
ls -lh "$DUMP"

# --- Retention: keep the 14 newest dumps ---
OLD_COUNT="$(ls -1t "$OUT_DIR"/leadstream_*.dump 2>/dev/null | tail -n +15 | wc -l)"
if [ "$OLD_COUNT" -gt 0 ]; then
  ls -1t "$OUT_DIR"/leadstream_*.dump 2>/dev/null | tail -n +15 | xargs rm -f
  echo "🧹 Pruned $OLD_COUNT old backup(s) — keeping 14 newest in $OUT_DIR"
else
  echo "Retention: 14 newest kept in $OUT_DIR"
fi
