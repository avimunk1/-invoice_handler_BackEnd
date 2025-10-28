# SQLAlchemy Core Migration

This document describes the migration from raw asyncpg to SQLAlchemy Core.

## Overview

The backend has been migrated from using raw asyncpg SQL queries to SQLAlchemy Core (query builder, not ORM). This provides:

- **Type-safe queries** - Column references are validated at import time
- **Cleaner upsert syntax** - `on_conflict_do_update()` instead of raw SQL
- **Better composition** - Easier to build dynamic queries
- **Migration management** - Alembic for version-controlled schema changes
- **No performance loss** - SQLAlchemy Core uses asyncpg under the hood

## Changes Made

### 1. Dependencies (`pyproject.toml`)
Added:
- `sqlalchemy[asyncio]==2.0.36` - Core library with async support
- `alembic==1.13.3` - Migration tool

### 2. New Files

#### `src/invoice_handler/models_db.py`
Defines all database tables using SQLAlchemy Core `Table` objects:
- `customers`
- `users`
- `expense_accounts`
- `suppliers`
- `invoices`

All tables include:
- Column definitions with types
- Foreign keys with proper ondelete behavior
- Unique constraints
- Check constraints
- Indexes

#### `src/invoice_handler/database.py`
Database connection management:
- `get_engine()` - Returns singleton async engine
- `close_engine()` - Cleanup on shutdown

#### `alembic/` Directory
Migration framework:
- `alembic.ini` - Configuration
- `alembic/env.py` - Async-compatible migration runner
- `alembic/versions/` - Migration files

### 3. Modified Files

#### `src/invoice_handler/config.py`
No changes needed - `database_url` already existed

#### `src/invoice_handler/main.py`
Major refactoring:

**Before (asyncpg):**
```python
pool = await asyncpg.create_pool(dsn=dsn)
async with pool.acquire() as conn:
    row = await conn.fetchrow("SELECT id FROM suppliers WHERE...")
```

**After (SQLAlchemy Core):**
```python
engine = get_engine()
async with engine.begin() as conn:
    stmt = select(suppliers.c.id).where(suppliers.c.customer_id == customer_id)
    result = await conn.execute(stmt)
    row = result.first()
```

**Key Changes:**

1. **Imports** - Added SQLAlchemy imports, removed asyncpg
2. **Startup/Shutdown** - Simplified to just call `close_engine()`
3. **`_ensure_supplier()`** - Rewritten with Core statements:
   - `update()` for updating supplier name
   - `select()` for finding existing supplier
   - `insert()` for creating new supplier
4. **`save_invoices_batch()`** - Major rewrite:
   - Uses `pg_insert()` for PostgreSQL-specific insert
   - `.on_conflict_do_update()` for upsert logic
   - JSONB serialization handled automatically
   - Transaction management via `engine.begin()`

## Benefits

### 1. Cleaner Upsert
**Before:**
```sql
INSERT INTO invoices (...) VALUES ($1,$2,$3,...)
ON CONFLICT (customer_id, supplier_id, invoice_number)
DO UPDATE SET field1 = EXCLUDED.field1, field2 = EXCLUDED.field2, ...
RETURNING id
```

**After:**
```python
stmt = pg_insert(invoices).values(...).on_conflict_do_update(
    index_elements=['customer_id', 'supplier_id', 'invoice_number'],
    set_={...}
).returning(invoices.c.id)
```

### 2. JSONB Handling
**Before:**
```python
metadata_json = json.dumps(inv.ocr_metadata) if inv.ocr_metadata else None
# Then pass as string
```

**After:**
```python
ocr_metadata=inv.ocr_metadata  # SQLAlchemy handles serialization
```

### 3. Type Safety
**Before:**
```python
row = await conn.fetchrow("SELECT id FROM suppliers WHERE customer_id = $1")
supplier_id = row["id"]  # String key, no IDE autocomplete
```

**After:**
```python
stmt = select(suppliers.c.id).where(suppliers.c.customer_id == customer_id)
result = await conn.execute(stmt)
row = result.first()
supplier_id = row.id  # Attribute access, IDE knows the schema
```

### 4. Migration Management
**Before:**
- Manual `schema.sql` file
- No version tracking
- No way to rollback changes

**After:**
- Version-controlled migrations in `alembic/versions/`
- Can upgrade/downgrade between versions
- Auto-generate migrations from model changes
- Clear audit trail of schema changes

## Usage

### Running the Backend
No changes needed to the startup script:
```bash
./backend_Start.sh
```

### Making Schema Changes

1. Edit `src/invoice_handler/models_db.py`
2. Generate migration:
   ```bash
   uv run alembic revision --autogenerate -m "add new column"
   ```
3. Review generated migration in `alembic/versions/`
4. Apply migration:
   ```bash
   uv run alembic upgrade head
   ```

See [ALEMBIC_USAGE.md](./ALEMBIC_USAGE.md) for detailed Alembic commands.

## Testing

The backend was tested to ensure:
- ✅ Imports successfully
- ✅ Database connection works
- ✅ Existing API endpoints unchanged
- ✅ Upsert logic preserved
- ✅ Supplier auto-creation works
- ✅ Transaction management intact

## Rollback Plan

If issues arise, rollback is straightforward:
1. Revert commits for `main.py`, `database.py`, `models_db.py`
2. Remove `alembic/` directory
3. Update `pyproject.toml` to remove SQLAlchemy/Alembic
4. Run `uv sync`

The database schema itself is unchanged, so no data migration needed.

## Next Steps

Consider:
- Add more endpoints using SQLAlchemy Core (list invoices, suppliers, etc.)
- Use Core's query composition for filtering/pagination
- Add database indexes via migrations as needed
- Consider using SQLAlchemy sessions for read-heavy operations

