from celery import Celery
from celery.schedules import crontab

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
    "collect-vm-metrics": {
        "task": "collect_vm_metrics",
        "schedule": 300.0,
    },
    "analyze-vm-optimizations": {
        "task": "analyze_vm_optimizations",
        "schedule": 300.0,
    },
    # Every Monday at 09:00 MSK (= 06:00 UTC)
    "send-weekly-ai-report": {
        "task": "send_weekly_ai_report",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),
    },
}
