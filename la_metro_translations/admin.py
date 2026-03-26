from django.contrib import admin
from la_metro_translations.models import (
    Document,
    DocumentContent,
    DocumentTranslation,
    TranslationFile,
)

admin.site.register(Document)
admin.site.register(DocumentContent)
admin.site.register(DocumentTranslation)
admin.site.register(TranslationFile)
