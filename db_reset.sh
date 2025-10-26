#!/bin/bash
# Reset local development database (DELETES ALL DATA)

set -e

cd "$(dirname "$0")"

echo "⚠️  WARNING: This will DELETE ALL DATA in the local database!"
read -p "Are you sure? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Aborted"
    exit 1
fi

echo "🗑️  Stopping and removing database..."
docker-compose down -v

echo "🐘 Starting fresh database..."
docker-compose up -d

# Wait for database to be healthy
echo "⏳ Waiting for database to be ready..."
timeout 30 bash -c 'until docker-compose exec -T postgres pg_isready -U dev -d invoice_handler_dev > /dev/null 2>&1; do sleep 1; done' || {
    echo "❌ Database failed to start within 30 seconds"
    exit 1
}

echo "✅ Database reset complete!"
echo ""
echo "Next steps:"
echo "  1. Run migrations: alembic upgrade head"
echo "  2. (Optional) Seed data"

