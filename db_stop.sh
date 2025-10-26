#!/bin/bash
# Stop local development database

set -e

cd "$(dirname "$0")"

echo "🛑 Stopping PostgreSQL database..."
docker compose down

echo "✅ Database stopped"

