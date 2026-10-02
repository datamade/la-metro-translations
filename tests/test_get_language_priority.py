import pytest
from conftest import TranslationConfigFactory
from la_metro_translations.models import DocumentTranslation


@pytest.mark.django_db
def test_language_priority():
    """
    Test that `get_language_priority` gets languages in the correct order.
    By default, sort order is determined by creation order.
    """
    spa = TranslationConfigFactory(language="spa", sort_order=0)
    vie = TranslationConfigFactory(language="vie", sort_order=1)
    zho = TranslationConfigFactory(language="zho-tw", sort_order=2)

    assert DocumentTranslation.get_language_priority() == ["spa", "vie", "zho-tw"]

    vie.sort_order = 0
    vie.save()

    zho.sort_order = 1
    zho.save()

    spa.sort_order = 2
    spa.save()

    assert DocumentTranslation.get_language_priority() == ["vie", "zho-tw", "spa"]
