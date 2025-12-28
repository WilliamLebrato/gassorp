#!/bin/bash

echo "🛑 Stopping GSP Development Environment..."
echo ""

docker-compose -f docker-compose.dev.yml down

echo ""
echo "✅ All containers stopped"
echo ""
echo "💾 To remove volumes as well, run: docker-compose -f docker-compose.dev.yml down -v"
