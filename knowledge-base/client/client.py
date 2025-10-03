from celery import Celery

app = Celery(
    "KnowledgeBase-Client",
    broker='redis://localhost:6379/0',
    backend="redis://localhost:6379/0"
)
