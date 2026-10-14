from django.db import migrations

APP = "la_metro_translations"
SKIP = ["id", "language"]

def merge_or_split_models(*, source, destination):
    merge = isinstance(source, list)
    separate_models = source if merge else destination

    for model in separate_models:
        all_cols = model._meta.concrete_fields
        cols_to_copy = [f.name for f in all_cols if f.name not in SKIP]
        if merge:
            for row in model.objects.all():
                copy_row(destination, row, cols_to_copy)
        else:
            for row in source.objects.all():
                copy_row(model, row, cols_to_copy)

def copy_row(dest_model, row, cols):
    dest_model.objects.update_or_create(
        language=row.language,
        defaults={col: getattr(row, col) for col in cols}
    )

def forwards(apps, _schema_editor):
    StandardTranslations = apps.get_model(APP, "StandardTranslations")
    LinkText = apps.get_model(APP, "LinkText")
    Disclaimer = apps.get_model(APP, "Disclaimer")
    merge_or_split_models(
        source=[LinkText, Disclaimer],
        destination=StandardTranslations
    )

def backwards(apps, _schema_editor):
    StandardTranslations = apps.get_model(APP, "StandardTranslations")
    LinkText = apps.get_model(APP, "LinkText")
    Disclaimer = apps.get_model(APP, "Disclaimer")
    merge_or_split_models(
        source=StandardTranslations,
        destination=[LinkText, Disclaimer]
    )

class Migration(migrations.Migration):
    dependencies = [(APP, "0026_standardtranslations")]
    operations = [migrations.RunPython(forwards, backwards)]
