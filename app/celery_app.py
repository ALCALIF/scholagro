from __future__ import annotations
from celery import Celery
from typing import Optional

def make_celery(app=None, broker_url: Optional[str] = None):
    # Accept app or create via environment
    if app is None:
        raise RuntimeError('Flask app instance required to configure Celery')
    broker = broker_url or app.config.get('CELERY_BROKER_URL') or app.config.get('REDIS_URL')
    backend = app.config.get('CELERY_RESULT_BACKEND') or broker
    celery = Celery(app.import_name, broker=broker, backend=backend)
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery
