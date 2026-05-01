from django.conf import settings
from django.utils.module_loading import import_string

from .conversion import DocumentTranslationConverter  # noqa
from .ocr import MistralOCRService  # noqa
from .translation import DummyTranslationService, MistralTranslationService  # noqa


def get_translation_service():
    return import_string(settings.TRANSLATION_SERVICE)
