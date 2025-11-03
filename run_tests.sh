#!/bin/bash
# Test runner script for METAR Calendar project

set -e

echo "Running METAR Calendar test suite..."
echo

# Run tests with coverage if --coverage flag is passed
if [ "$1" = "--coverage" ]; then
    echo "Running with coverage report..."
    python -m pytest tests/ \
        --cov=lib \
        --cov=cli \
        --cov=website/backend \
        --cov-report=term-missing \
        --cov-report=html
    echo
    echo "HTML coverage report generated in htmlcov/index.html"
else
    python -m pytest tests/ -v
fi
