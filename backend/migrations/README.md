# Database Migrations

This project uses **Alembic** for database schema migrations.

## Current State

- **Baseline migration**: `001_baseline` - Captures the complete schema as of 2026-08-29
- **Database**: PostgreSQL (Neon)
- **ORM**: Raw psycopg2 (no SQLAlchemy models)

## Important: Autogenerate Limitation

Because this project uses **raw psycopg2** instead of SQLAlchemy declarative models, **`alembic revision --autogenerate` will not work correctly**. It will detect all tables as "removed" because there's no SQLAlchemy metadata to compare against.

## Migration Workflow

### For New Schema Changes

1. **Create a new manual migration:**
   ```bash
   python -m alembic revision -m "description_of_change"
   ```

2. **Edit the generated file** to add `upgrade()` and `downgrade()` operations using SQLAlchemy DDL or raw SQL:
   ```python
   def upgrade() -> None:
       op.execute("ALTER TABLE leads_raw ADD COLUMN new_field TEXT")
       # or
       op.add_column('leads_raw', sa.Column('new_field', sa.Text()))
   
   def downgrade() -> None:
       op.execute("ALTER TABLE leads_raw DROP COLUMN new_field")
   ```

3. **Test the migration:**
   ```bash
   python -m alembic upgrade head
   ```

4. **Commit the migration file** with your code changes.

### Useful Commands

```bash
# Show current migration
python -m alembic current

# Show migration history
python -m alembic history

# Upgrade to latest
python -m alembic upgrade head

# Downgrade one step
python -m alembic downgrade -1

# Show SQL without executing
python -m alembic upgrade head --sql
```

## Migration File Structure

```
migrations/
├── alembic.ini          # Alembic configuration
├── env.py               # Environment setup (loads .env from app/.env)
├── script.py.mako       # Template for new migrations
├── versions/
│   ├── 001_baseline.py  # Baseline schema (DO NOT MODIFY)
│   └── ...              # Future manual migrations
└── README.md            # This file
```

## Environment Variables

Migrations load configuration from `backend/app/.env`:
- `DATABASE_URL` - PostgreSQL connection string

## Production Deployment

On Render, migrations run automatically via the build script. Ensure `DATABASE_URL` is set in the environment.

## Adding a Column Example

```bash
# 1. Create migration
python -m alembic revision -m "add_new_field_to_leads"

# 2. Edit the file (e.g., migrations/versions/xxx_add_new_field_to_leads.py)
#    Add the column in upgrade(), remove in downgrade()

# 3. Apply
python -m alembic upgrade head
```

## Reverting a Migration

```bash
# Revert last migration
python -m alembic downgrade -1

# Revert to specific revision
python -m alembic downgrade 001_baseline
```