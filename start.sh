#!/bin/bash

set -e

echo "🎮 Game Server Platform - Startup Script"

if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your configuration."
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🚀 Starting the server..."
python3 main.py
