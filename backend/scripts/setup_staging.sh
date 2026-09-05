#!/bin/bash
# Staging Environment Setup Script
#
# Creates a staging environment separate from production:
# - Separate PostgreSQL database
# - Separate Redis namespace
# - Test Gmail account (NOT production)
# - Same codebase, different config
#
# Usage: ./scripts/setup_staging.sh
#
# Prerequisites:
# - DATABASE_URL_STAGING env var set
# - REDIS_URL_STAGING env var set
# - Test Gmail OAuth credentials configured

set -e

echo "🔧 STAGING ENVIRONMENT SETUP"
echo "============================"

# Check required env vars
if [ -z "$DATABASE_URL_STAGING" ]; then
    echo "❌ DATABASE_URL_STAGING not set"
    echo "Set it to your staging PostgreSQL URL"
    exit 1
fi

if [ -z "$REDIS_URL_STAGING" ]; then
    echo "⚠️  REDIS_URL_STAGING not set — using default"
    REDIS_URL_STAGING="redis://localhost:6379/1"
fi

echo ""
echo "Database: $DATABASE_URL_STAGING"
echo "Redis: $REDIS_URL_STAGING"
echo ""

# Create staging .env file
cat > .env.staging << EOF
# Staging Environment Configuration
# Generated: $(date)

# Database
DATABASE_URL=$DATABASE_URL_STAGING
DB_POOL_MIN=1
DB_POOL_MAX=5

# Redis
REDIS_URL=$REDIS_URL_STAGING

# Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=staging_admin_$(openssl rand -hex 8)

# Gmail (USE TEST ACCOUNT ONLY)
# NEVER use production Gmail credentials in staging
GOOGLE_CLIENT_ID=staging_client_id
GOOGLE_CLIENT_SECRET=staging_client_secret
GOOGLE_REDIRECT_URI=https://staging.leadstreamai.onrender.com/api/auth/google/callback

# URLs
BACKEND_URL=https://staging-backend.onrender.com
FRONTEND_URL=https://staging.leadstreamai.onrender.com

# Security
TOKEN_ENCRYPTION_KEY=staging_encryption_$(openssl rand -hex 16)

# Scheduler (staging can be more aggressive)
SCHEDULER_FOLLOWUP_INTERVAL_SEC=5
SCHEDULER_SCHEDULED_INTERVAL_SEC=10

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json
DEBUG=true
EOF

echo "✅ Created .env.staging"

# Run database migration
echo ""
echo "Running database migration..."
DATABASE_URL="$DATABASE_URL_STAGING" python -c "
from app.database import create_tables
create_tables()
print('✅ Database tables created/updated')
"

# Seed test data
echo ""
echo "Seeding test data..."
DATABASE_URL="$DATABASE_URL_STAGING" python -c "
from app.database import get_db_connection
conn = get_db_connection()
cur = conn.cursor()

# Check if staging admin exists
cur.execute(\"SELECT COUNT(*) FROM users WHERE username = 'staging_admin'\")
count = cur.fetchone()[0]

if count == 0:
    import bcrypt
    import os
    from dotenv import load_dotenv
    load_dotenv('.env.staging')

    password = os.getenv('ADMIN_PASSWORD', 'staging_test')
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cur.execute('''
        INSERT INTO users (username, email, full_name, password_hash, role, is_active, is_approved)
        VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
    ''', ('staging_admin', 'staging@leadstreamai.com', 'Staging Admin', password_hash, 'ADMIN'))
    conn.commit()
    print('✅ Staging admin user created')
else:
    print('✅ Staging admin already exists')

cur.close()
conn.close()
"

echo ""
echo "============================"
echo "✅ Staging environment ready!"
echo ""
echo "Next steps:"
echo "1. Deploy staging backend with .env.staging"
echo "2. Deploy staging frontend with VITE_API_BASE_URL=https://staging-backend.onrender.com"
echo "3. Connect TEST Gmail account (not production)"
echo "4. Run smoke tests against staging"
echo "5. Verify CI/CD pipeline targets staging"
echo ""
echo "⚠️  CRITICAL: Never use production Gmail credentials in staging!"
