#!/bin/bash

echo "🛑 Stopping GSP Microservices..."

docker-compose down

echo ""
echo "✅ All services stopped!"
echo ""
echo "🧹 Clean up volumes:  docker-compose down -v"
echo "🗑️  Remove images:     docker-compose down --rmi all"
echo ""
