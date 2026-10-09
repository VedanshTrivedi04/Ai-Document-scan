#!/bin/sh
# Single-worker script for Render free tier.
# Runs ALL queues in one Celery process instead of 4 separate containers.
# Pool = threads (works on free-tier Linux without prefork overhead).
# Concurrency = 2 (fits within 512 MB RAM on Render free).
set -e
exec celery -A app.tasks.celery_app worker \
  --queues=extraction_queue,vision_queue,forensics_queue,housekeeping_queue,celery \
  --hostname=all-in-one@%h \
  --concurrency=2 \
  --pool=threads \
  --loglevel=info
