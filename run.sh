#!/bin/bash

MAX_RETRIES=3
RETRY_COUNT=0
SUCCESS=false

echo "🚀 Starting GSP Development Environment..."
echo ""

# Check if .env files exist
if [ ! -f .env ]; then
    echo "⚠️  Root .env not found, copying from .env.example..."
    cp .env.example .env
fi

if [ ! -f backend/.env ]; then
    echo "⚠️  Backend .env not found, copying from .env.example..."
    cp backend/.env.example backend/.env
fi

if [ ! -f frontend/.env ]; then
    echo "⚠️  Frontend .env not found, copying from .env.example..."
    cp frontend/.env.example frontend/.env
fi

echo "✅ Environment files ready"
echo ""

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    
    if [ $RETRY_COUNT -gt 1 ]; then
        echo ""
        echo "🔄 Retry attempt $RETRY_COUNT of $MAX_RETRIES..."
        echo ""
    fi
    
    echo "📦 Building and starting containers..."
    echo ""
    
    if docker-compose -f docker-compose.dev.yml up --build; then
        SUCCESS=true
        echo ""
        echo "✅ Containers stopped successfully"
        exit 0
    else
        EXIT_CODE=$?
        echo ""
        echo "❌ Startup failed with exit code: $EXIT_CODE"
        
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "⏳ Waiting 5 seconds before retry..."
            sleep 5
        fi
    fi
done

echo ""
echo "💥 Failed after $MAX_RETRIES attempts. Giving up."
echo "🛑 Stopping containers..."
docker-compose -f docker-compose.dev.yml down
exit 1
