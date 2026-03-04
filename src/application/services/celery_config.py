from celery import Celery

from src.settings import settings

celery_app = Celery(
    __name__,
    broker=settings.redis.url,
    backend=settings.redis.url,
    broker_connection_retry_on_startup=True,
    include=["src.application.services.tasks"]
)

celery_app.conf.beat_schedule = {
    "sync-vm-statuses": {
        "task": "sync_vm_statuses",
        "schedule": 60.0,
    },
    "cleanup-terminated": {
        "task": "cleanup_terminated_vms",
        "schedule": 3600.0,
    },
}
