import os
import sys

from celery import Celery

# Shared with Settings.redis_url so the two cannot drift. Celery binds its
# broker when the module is imported -- before FastAPI's lifespan has run and
# before any .env is required -- so this one value is read from the
# environment directly rather than through Settings. Importing a module must
# cost nothing and demand nothing, or CI cannot import the app without secrets.
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

broker_url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)

celery_app = Celery(
    "omniassist",
    broker=broker_url,
    backend=broker_url,
    # The worker imports this module, not the one tasks live in, so without
    # `include` nothing is registered and every job fails with NotRegistered
    # -- which only a running worker reveals.
    include=["app.jobs.indexing"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Results are a progress indicator, not a record. The database holds
    # anything that matters, so letting them expire costs nothing.
    result_expires=3600,
    # Acknowledge after the task finishes, not when it is received: a worker
    # killed mid-task would otherwise lose the job silently.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # macOS restricts fork() in a process that has already initialised certain
    # frameworks, and Celery's default prefork pool then starts children with
    # no task registry -- every job fails with an unpacking error from deep
    # inside billiard, which looks like anything but a platform problem.
    # Linux, where this deploys, keeps prefork.
    worker_pool="solo" if sys.platform == "darwin" else "prefork",
)
