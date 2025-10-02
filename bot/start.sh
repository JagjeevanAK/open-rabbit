#!/bin/bash

set -e

echo "GitHub Bot Quick Start"
echo ""

if [ ! -f .env ]; then
    echo "No .env file found!"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env file"
        echo "Please edit .env and add your GitHub App credentials!"
        echo ""
        read -p "Press Enter after you've configured .env..."
    else
        echo ".env.example not found. Please create a .env file manually."
        exit 1
    fi
fi

if [ ! -d node_modules ]; then
    echo "Installing dependencies..."
    npm install
    echo "Dependencies installed"
    echo ""
fi

if [ ! -d lib ]; then
    echo "Building TypeScript code..."
    npm run build
    echo "Build complete"
    echo ""
fi

if [ "$(find src -type f -newer lib 2>/dev/null | head -1)" ]; then
    echo "Source files changed, rebuilding..."
    npm run build
    echo "Build complete"
    echo ""
fi

echo "Starting the bot..."
echo "   Press Ctrl+C to stop"
echo ""
npm start
