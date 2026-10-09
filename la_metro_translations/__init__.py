# Load the Celery app when Django starts so that @shared_task uses it
from .celery import app as celery_app

__all__ = ("celery_app",)

default_app_config = "la_metro_translations.apps.LaMetroTranslationsConfig"
