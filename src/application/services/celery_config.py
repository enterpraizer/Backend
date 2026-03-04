from celery import Celery

from src.settings import settings

celery_app = Celery(
    __name__,
    broker=settings.redis.url,
    backend=settings.redis.url,
    broker_connection_retry_on_startup=True,
    include=["src.application.services.tasks"]
)
