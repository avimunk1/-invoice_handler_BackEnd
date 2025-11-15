#!/usr/bin/env python3
"""
Seed script to create a test customer in the database.
Run with: uv run python seed_customer.py
"""
import asyncio
from sqlalchemy import select
from src.invoice_handler.database import get_engine
from src.invoice_handler.models_db import customers


async def seed_customer():
    """Create a test customer with id=1 if it doesn't exist."""
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Check if customer with id=1 already exists
        stmt = select(customers).where(customers.c.id == 1)
        result = await conn.execute(stmt)
        existing = result.first()
        
        if existing:
            print(f"✅ Customer already exists: id={existing.id}, name='{existing.name}'")
        else:
            # Insert test customer
            stmt = customers.insert().values(
                name="Test Customer",
                active=True
            )
            result = await conn.execute(stmt)
            print(f"✅ Created test customer with id=1, name='Test Customer'")
    
    # Close engine
    from src.invoice_handler.database import close_engine
    await close_engine()
    print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(seed_customer())

