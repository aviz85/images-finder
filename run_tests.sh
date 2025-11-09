#!/bin/bash
# Script to run tests with coverage

set -e

echo "Running tests with coverage..."
echo "========================================"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run pytest with coverage
pytest \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=json \
    -v \
    "$@"

echo ""
echo "========================================"
echo "Coverage report generated in htmlcov/"
echo "Open htmlcov/index.html to view detailed coverage"
echo ""
echo "To run only unit tests:"
echo "  pytest tests/ -m 'not integration'"
echo ""
echo "To run only integration tests:"
echo "  pytest tests/ -m integration"
echo ""
