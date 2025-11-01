#!/bin/bash
# Development environment startup script
# Runs both the CherryPy backend and Jekyll frontend in parallel

set -e

cd "$(dirname "$0")"

echo "Starting development environment..."
echo "Backend will be available at: http://localhost:5000"
echo "Frontend will be available at: http://localhost:4000"
echo ""

# Run backend and frontend in parallel
(cd backend && python app.py) & \
(cd frontend && bundle exec jekyll serve --config _config.yml,_config_dev.yml)
