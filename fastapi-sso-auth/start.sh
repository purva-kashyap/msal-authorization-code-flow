#!/bin/bash
# Quick start script for FastAPI SSO app

echo "=========================================="
echo "FastAPI SSO Authentication - Quick Start"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env and add your Azure AD credentials:"
    echo "   - CLIENT_ID"
    echo "   - CLIENT_SECRET"
    echo "   - TENANT_ID"
    echo ""
    echo "🔑 Generate secrets by running:"
    echo "   python generate_secrets.py"
    echo ""
    exit 1
fi

# Check if PostgreSQL is running
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL client not found. Please install PostgreSQL."
    exit 1
fi

# Check if database exists
if ! psql -lqt | cut -d \| -f 1 | grep -qw entra_tokens; then
    echo "📦 Creating database 'entra_tokens'..."
    createdb entra_tokens 2>/dev/null || {
        echo "⚠️  Failed to create database. Please run:"
        echo "   createdb entra_tokens"
        exit 1
    }
fi

echo "✅ Database ready"
echo ""
echo "🚀 Starting FastAPI server..."
echo ""

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
