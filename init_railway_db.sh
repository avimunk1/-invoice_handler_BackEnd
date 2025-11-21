#!/bin/bash
# Initialize Railway PostgreSQL database
# Usage: DATABASE_URL="your-railway-db-url" ./init_railway_db.sh

if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    echo "Get it from Railway: PostgreSQL service → Variables tab → DATABASE_URL"
    echo "Then run: DATABASE_URL='your-url' ./init_railway_db.sh"
    exit 1
fi

echo "Initializing Railway database..."
psql "$DATABASE_URL" -f init_db/init_railway.sql

if [ $? -eq 0 ]; then
    echo "✓ Database initialized successfully!"
else
    echo "✗ Database initialization failed"
    exit 1
fi

