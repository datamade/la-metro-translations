import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "la_metro_translations.settings")

app = Celery("la_metro_translations")

# Read config from Django settings, using the CELERY_ prefix for Celery keys
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
