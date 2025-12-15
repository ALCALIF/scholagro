from app import create_app
from app.tasks import init_celery

app = create_app()
celery = init_celery(app)

if __name__ == '__main__':
    # For development: run worker via `python celery_worker.py`
    celery.worker_main()
