#!/bin/sh
set -e
# Apply migrations, ensure the seeded admin exists, then serve the API.
alembic upgrade head
python seed.py

# In Render Free Web Service, run Celery worker in background so a paid worker service is not needed
if [ "${RUN_EMBEDDED_WORKER:-true}" = "true" ]; then
  echo "Starting embedded Celery worker for background tasks..."
  celery -A app.tasks.celery_app worker \
    --queues=extraction_queue,vision_queue,forensics_queue,housekeeping_queue,celery \
    --hostname=embedded-worker@%h \
    --concurrency=2 \
    --pool=threads \
    --loglevel=info &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

