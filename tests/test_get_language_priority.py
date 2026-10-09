import pytest
from conftest import TranslationConfigFactory
from la_metro_translations.models import DocumentTranslation


@pytest.mark.django_db
def test_language_priority():
    """
    Test that `get_language_priority` gets languages in the correct order.
    By default, sort order is determined by creation order, with English prepended.
    """
    spa = TranslationConfigFactory(language="spa")
    vie = TranslationConfigFactory(language="vie")
    zho = TranslationConfigFactory(language="zho-tw")

    assert DocumentTranslation.get_language_priority() == [
        "eng",
        "spa",
        "vie",
        "zho-tw",
    ]

    vie.sort_order = 0
    vie.save()

    zho.sort_order = 1
    zho.save()

    spa.sort_order = 2
    spa.save()

    assert DocumentTranslation.get_language_priority() == [
        "eng",
        "vie",
        "zho-tw",
        "spa",
    ]
