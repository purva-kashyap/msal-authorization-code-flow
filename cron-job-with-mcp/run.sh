#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Error: .env file not found in cron-job-with-mcp"
  exit 1
fi

export $(cat .env | grep -v '^#' | xargs)
python cron_job.py
