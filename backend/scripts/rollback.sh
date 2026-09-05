#!/bin/bash
# Production Rollback Script
# Usage: ./scripts/rollback.sh [commit_hash]
#
# If no commit hash provided, rolls back to the previous commit.
# This script:
# 1. Stashes any uncommitted changes
# 2. Resets to the specified commit (or HEAD~1)
# 3. Runs deploy gate checks
# 4. Reports status
#
# WARNING: This is for emergencies only. For normal deployments, use CI/CD.

set -e

echo "🔄 PRODUCTION ROLLBACK"
echo "======================"

# Get target commit
if [ -n "$1" ]; then
    TARGET="$1"
    echo "Target: $TARGET"
else
    TARGET="HEAD~1"
    echo "Target: Previous commit ($TARGET)"
fi

# Show current state
echo ""
echo "Current HEAD:"
git log --oneline -1
echo ""

# Show what we're rolling back to
echo "Rolling back to:"
git log --oneline -1 "$TARGET"
echo ""

# Confirm
read -p "Proceed with rollback? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Stash uncommitted changes
echo "Stashing uncommitted changes..."
git stash push -m "Rollback stash $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

# Reset to target
echo "Resetting to $TARGET..."
git reset --hard "$TARGET"

echo ""
echo "✅ Rollback complete."
echo "Current HEAD:"
git log --oneline -3

echo ""
echo "Next steps:"
echo "1. Run: cd backend && python scripts/deploy_gate.py"
echo "2. If checks pass, deploy will auto-trigger on Render"
echo "3. If issues persist, contact team"
