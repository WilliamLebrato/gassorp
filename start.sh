#!/bin/bash

set -e

echo "🚀 Starting GSP Microservices..."

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your OAuth credentials"
fi

# Create necessary directories
mkdir -p backend/data game_data

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "✅ Services started!"
echo ""
echo "🌐 Frontend:     http://localhost:3000"
echo "📚 Backend API:  http://localhost:8000/docs"
echo "🤖 Node Agent:   http://localhost:8001/docs"
echo ""
echo "📊 View logs:    docker-compose logs -f"
echo "🛑 Stop all:     docker-compose down"
echo "🔄 Restart:      docker-compose restart"
echo ""
