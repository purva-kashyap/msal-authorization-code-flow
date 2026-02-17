#!/bin/bash
# Script to run the cron job manually for testing

set -e

# Change to script directory
cd "$(dirname "$0")"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Run the cron job
echo "Starting meeting transcript processing..."
echo "========================================"
python cron_job.py
echo "========================================"
echo "Processing complete!"
