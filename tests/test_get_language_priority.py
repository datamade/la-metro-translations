import pytest
from conftest import TranslationConfigFactory
from la_metro_translations.models import DocumentTranslation


@pytest.fixture
def lg_config(extraction_config):
    def build(**kwargs):
        kwargs.setdefault("config", extraction_config)
        return TranslationConfigFactory(**kwargs)

    return build


@pytest.mark.django_db
def test_language_priority(lg_config):
    """
    Test that `get_language_priority` gets languages in the correct order.
    By default, sort order is determined by creation order.
    """
    lgs = ["spa", "vie", "zho-tw"]

    lg_config(language=lgs[0])
    lg_config(language=lgs[1])
    lg_config(language=lgs[2])

    assert DocumentTranslation.get_language_priority() == lgs
