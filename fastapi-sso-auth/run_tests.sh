#!/bin/bash
# Test runner script for FastAPI SSO Authentication

set -e

# Disable problematic pytest plugins
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

echo "================================"
echo "FastAPI SSO Auth - Test Suite"
echo "================================"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install test dependencies
echo "Installing test dependencies..."
pip install pytest pytest-asyncio pytest-cov pytest-mock httpx aiosqlite -q

# Run tests based on argument
case "${1:-all}" in
    "unit")
        echo "Running unit tests..."
        python -m pytest -v -m unit tests/
        ;;
    "coverage")
        echo "Running tests with coverage..."
        python -m pytest --cov=app --cov-report=html --cov-report=term tests/
        echo ""
        echo "Coverage report generated in htmlcov/"
        echo "Open htmlcov/index.html to view"
        ;;
    "fast")
        echo "Running fast tests..."
        python -m pytest -v --tb=short tests/
        ;;
    "verbose")
        echo "Running tests with verbose output..."
        python -m pytest -vv tests/
        ;;
    "specific")
        if [ -z "$2" ]; then
            echo "Error: Please specify test file or test name"
            echo "Usage: ./run_tests.sh specific tests/test_encryption.py"
            exit 1
        fi
        echo "Running specific test: $2"
        python -m pytest -v "$2"
        ;;
    *)
        echo "Running all tests..."
        python -m pytest -v tests/
        ;;
esac

echo ""
echo "✅ Tests completed!"
