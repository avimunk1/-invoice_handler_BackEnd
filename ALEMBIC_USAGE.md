# Alembic Database Migrations

This project now uses Alembic for managing database schema changes.

## Setup for Existing Database

Since the database was already initialized with `init_db/schema.sql`, we need to mark it as being at the initial migration:

```bash
cd backend
uv run alembic stamp head
```

This tells Alembic that the database is already at the "head" revision without running any migrations.

## Common Commands

### Check Current Revision
```bash
uv run alembic current
```

### Create a New Migration
After modifying tables in `src/invoice_handler/models_db.py`:

```bash
# Auto-generate migration
uv run alembic revision --autogenerate -m "description of changes"

# Or create empty migration template
uv run alembic revision -m "description of changes"
```

### Apply Migrations
```bash
# Upgrade to latest
uv run alembic upgrade head

# Upgrade one version
uv run alembic upgrade +1

# Downgrade one version
uv run alembic downgrade -1
```

### View Migration History
```bash
uv run alembic history

# Verbose with diffs
uv run alembic history --verbose
```

### Rollback to Specific Version
```bash
uv run alembic downgrade <revision_id>
```

## Making Schema Changes

1. **Modify** `src/invoice_handler/models_db.py` - Update table definitions
2. **Generate** migration: `uv run alembic revision --autogenerate -m "add column xyz"`
3. **Review** the generated migration in `alembic/versions/`
4. **Test** locally: `uv run alembic upgrade head`
5. **Commit** both the models_db.py and the migration file

## Important Notes

- Always review auto-generated migrations before applying
- Test migrations on development database first
- Alembic uses the `DATABASE_URL` from your environment or `.env` file
- Migrations run in async mode using asyncpg
- The `alembic_version` table tracks which migrations have been applied

## Configuration

- **alembic.ini** - Main configuration file
- **alembic/env.py** - Migration environment (imports metadata, handles async)
- **alembic/versions/** - Migration files (auto-generated)

