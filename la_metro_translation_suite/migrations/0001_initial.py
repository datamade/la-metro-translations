from django.db import migrations, models

import wagtail


class Migration(migrations.Migration):
    dependencies = [
        ("wagtailcore", "0095_groupsitepermission"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaticPage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.Page",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("wagtailcore.page",),
        ),
        migrations.AddField(
            model_name="StaticPage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    ("content", wagtail.blocks.RichTextBlock()),
                    ("image", wagtail.images.blocks.ImageChooserBlock()),
                ],
                blank=True,
            ),
        ),
    ]
