#!/usr/bin/env python3
"""
Initialize Railway database with the full init_railway.sql script
Run with: DATABASE_URL="your-url" python run_init_sql.py
"""
import asyncio
import asyncpg
import os
import sys

async def run_init_sql():
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)
    
    print(f"Connecting to Railway database...")
    print(f"Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'unknown'}")
    
    try:
        # Set a longer timeout for the connection
        conn = await asyncpg.connect(database_url, timeout=30)
        print("✓ Connected successfully!")
        
        # Read the init SQL file
        print("\nReading init_railway.sql...")
        with open('init_db/init_railway.sql', 'r') as f:
            sql_content = f.read()
        
        # Execute the SQL
        print("Executing SQL statements...")
        await conn.execute(sql_content)
        
        print("\n✓ Database initialized successfully!")
        print("\nVerifying...")
        
        # Verify tables
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        print(f"\nTables created ({len(tables)}):")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Verify data
        customer_count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        expense_count = await conn.fetchval("SELECT COUNT(*) FROM expense_accounts")
        
        print(f"\nData seeded:")
        print(f"  - Customers: {customer_count}")
        print(f"  - Expense accounts: {expense_count}")
        
        await conn.close()
        print("\n✓ All done!")
        
    except asyncio.TimeoutError:
        print("\n✗ ERROR: Connection timeout")
        print("\nPlease ensure:")
        print("1. Public networking is ENABLED on your Railway PostgreSQL service")
        print("   (Settings → Networking → Enable Public Networking)")
        print("2. You're using the PUBLIC/EXTERNAL connection string")
        print("   (not the internal one with 'postgres.railway.internal')")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(run_init_sql())

