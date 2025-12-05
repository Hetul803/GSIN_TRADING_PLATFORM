#!/bin/bash
# Helper script to update DATABASE_URL in config/.env
# Usage: ./update_db_connection.sh "postgresql://..."

if [ -z "$1" ]; then
    echo "Usage: ./update_db_connection.sh 'postgresql://postgres:password@host:port/db'"
    echo ""
    echo "Or edit config/.env manually and set DATABASE_URL"
    exit 1
fi

# Update .env file
sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$1|" config/.env
echo "✅ Updated DATABASE_URL in config/.env"
echo ""
echo "Testing connection..."
python test_db_connection.py

