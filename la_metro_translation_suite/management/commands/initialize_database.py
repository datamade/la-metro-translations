# Based on the Wagtail demo:
# https://github.com/wagtail/bakerydemo/blob/master/bakerydemo/base/management/commands/load_initial_data.py
from django.db import transaction
from django.core.management.base import BaseCommand

from wagtail.models import Site, Page, Revision
from wagtail.rich_text import RichText

from la_metro_translation_suite.models import StaticPage, ExampleModel, ExampleModelDetailPage


class Command(BaseCommand):
    """
    Add starter content to empty database. Used in data migration.
    If you'd like to load an existing data fixture, see load_content.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-only",
            action="store_true",
            help="Delete but don't recreate pages",
        )

    @transaction.atomic
    def handle(self, **options):
        self.flush()

        if not options["flush_only"]:
            self.load_default_content()

    def flush(self):
        # Don't delete the default root page
        Page.objects.exclude(id=1).delete()
        Revision.objects.exclude(page__id=1).delete()
        ExampleModel.objects.all().delete()

    def load_default_content(self):
        root = Page.objects.get(id=1)

        if root.slug != "root":
            root.slug = "root"
            root.save_revision().publish()
            root.save()

        homepage = StaticPage(title="Home", slug="home", show_in_menus=True)

        homepage.body.extend(
            [
                ("content", RichText("<p>Welcome to the website!</p>")),
                (
                    "content",
                    RichText("<p>One day, it will contain very cool content.</p>"),
                ),
                (
                    "react_block",
                    {
                        "title": "React Block",
                        "description": RichText(
                            "<p>This React block can be added,"
                            + " reordered, or removed in the CMS!</p>"
                        ),
                    },
                ),
            ]
        )

        root.add_child(instance=homepage)
        homepage.save_revision().publish()

        site, _ = Site.objects.get_or_create(
            hostname="localhost", root_page=homepage, is_default_site=True
        )

        subpage = StaticPage(title="Example Page", show_in_menus=True)

        subpage.body.extend(
            [
                (
                    "content",
                    RichText(
                        "<p>This is an example subpage. "
                        "It, too, will one day contain compelling content.</p>"
                    ),
                ),
            ]
        )

        homepage.add_child(instance=subpage)
        subpage.save_revision().publish()

        model_root = StaticPage(title="Example Models", show_in_menus=True)
        homepage.add_child(instance=model_root)
        model_root.save()

        model_instance = ExampleModel.objects.create(name="Example Instance")

        model_detail = ExampleModelDetailPage(object=model_instance, show_in_menus=True)

        model_detail.body.extend(
            [
                (
                    "content",
                    RichText(
                        "<p>You can customize content based on the model instance"
                        + " by editing the page template.</p>"
                    ),
                ),
            ]
        )

        model_root.add_child(instance=model_detail)
        model_detail.save()
