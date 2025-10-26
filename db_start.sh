#!/bin/bash
# Start local development database

set -e

echo "🐘 Starting PostgreSQL database..."

cd "$(dirname "$0")"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Start database
docker-compose up -d

# Wait for database to be healthy
echo "⏳ Waiting for database to be ready..."
timeout 30 bash -c 'until docker-compose exec -T postgres pg_isready -U dev -d invoice_handler_dev > /dev/null 2>&1; do sleep 1; done' || {
    echo "❌ Database failed to start within 30 seconds"
    exit 1
}

echo "✅ Database is ready!"
echo ""
echo "📊 Database Information:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Database: invoice_handler_dev"
echo "   User: dev"
echo "   Password: dev123"
echo ""
echo "Connection string:"
echo "   postgresql://dev:dev123@localhost:5432/invoice_handler_dev"
echo ""
echo "To stop: cd backend && docker-compose down"
echo "To reset: cd backend && docker-compose down -v"

