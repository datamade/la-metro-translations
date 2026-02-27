from django.apps import AppConfig


class LaMetroTranslationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'la_metro_translations'

    def ready(self):
        # Import wagtail_hooks to ensure they are registered
        from . import wagtail_hooks