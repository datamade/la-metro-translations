from django.db import migrations

APP = "la_metro_translations"
OLD_MODELS = ["LinkText", "Disclaimer"]
SKIP = ["id", "language"]

def copy_over(apps, _schema_editor):
    new_model = apps.get_model(APP, "StandardTranslations")
    for model in OLD_MODELS:
        old_model = apps.get_model(APP, model)
        all_fields = old_model._meta.concrete_fields
        copy_fields = [f.name for f in all_fields if f.name not in SKIP]
        for row in old_model.objects.all():
            new_model.objects.update_or_create(
                language=row.language,
                defaults={key: getattr(row, key) for key in copy_fields}
            )

class Migration(migrations.Migration):
    dependencies = [(APP, "0026_standardtranslations")]
    operations = [migrations.RunPython(copy_over, migrations.RunPython.noop)]
