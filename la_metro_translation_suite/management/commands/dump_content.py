from pathlib import Path
import subprocess

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    """
    Dump core Wagtail content and any custom pages and/or Django models
    where the include_in_dump attribute is True. Also copy images uploaded
    locally to the fixtures directory, so that they can be loaded to default
    storage (usually S3) during deployment.
    """

    def handle(self, **options):
        app_models = apps.get_app_config("la_metro_translation_suite").get_models()

        excluded_app_models = [
            f"la_metro_translation_suite.{m.__name__}"
            for m in app_models
            if not getattr(m, "include_in_dump", False)
        ]

        call_command(
            "dumpdata",
            natural_foreign=True,
            indent=4,
            output=Path("la_metro_translation_suite/fixtures/cms_content.json"),
            exclude=[
                "contenttypes",
                "auth.permission",
                "wagtailcore.groupcollectionpermission",
                "wagtailcore.grouppagepermission",
                "sessions",
            ]
            + excluded_app_models,
        )

        subprocess.run(
            [
                "cp",
                "-R",
                "media/.",
                "la_metro_translation_suite/fixtures/initial_images/",
            ],
            check=True,
        )
