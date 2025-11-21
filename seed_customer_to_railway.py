#!/usr/bin/env python3
"""
Seed the default customer to Railway database
Run with: python seed_customer_to_railway.py
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def seed_customer():
    # Get DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return
    
    print(f"Connecting to database...")
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Insert default customer
        await conn.execute('''
            INSERT INTO customers (id, name, email, phone, address, created_at, updated_at)
            VALUES (
                1,
                'Default Customer',
                'default@example.com',
                NULL,
                NULL,
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
        ''')
        
        # Reset sequence
        await conn.execute('''
            SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers))
        ''')
        
        print("✓ Successfully seeded default customer (ID: 1)")
        
        await conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        raise

if __name__ == '__main__':
    asyncio.run(seed_customer())

