import functools

from django.contrib.auth.models import Permission, Group

import factory
import pytest

from django.contrib.contenttypes.models import ContentType
from la_metro_translations.models import Document, DocumentContent, DocumentTranslation


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "la_metro_translations.Document"

    title = "Test Document"
    source_url = "dummy url"
    document_type = "bill_document"
    document_id = 999
    entity_type = "bill"
    entity_id = 999


class DocumentContentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "la_metro_translations.DocumentContent"

    markdown = "Cost temperature personal today free star"
    approval_status = "approved"


class DocumentTranslationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "la_metro_translations.DocumentTranslation"

    markdown = "Jugar querer montaña quince, otro gris más"
    language = "sp"
    approval_status = "waiting"


@pytest.fixture
def document():
    return DocumentFactory()


@pytest.fixture
def document_content(document):
    return DocumentContentFactory(document=document)


@pytest.fixture
def document_translation(document_content):
    return DocumentTranslationFactory(document_content=document_content)


@pytest.fixture
def client(client):
    """We enforce SSL in production (see settings.py) so test clients
    must also use SSL to work properly."""
    client.get = functools.partial(client.get, secure=True)
    client.post = functools.partial(client.post, secure=True)
    return client


@pytest.fixture
def super_user_client(admin_client):
    return admin_client


@pytest.fixture
def wagtail_user_group():
    # Create a group with Wagtail access and Document* model permissions
    wagtail_group = Group.objects.create(name="Wagtail Document Editors")

    # Add Wagtail admin access permission
    wagtail_permission = Permission.objects.get(
        content_type__app_label="wagtailadmin", codename="access_admin"
    )
    wagtail_group.permissions.add(wagtail_permission)

    # Add model-specific permissions for the custom viewsets
    models = [Document, DocumentContent, DocumentTranslation]
    for model in models:
        content_type = ContentType.objects.get_for_model(model)

        # Add view and change permissions for each model
        for action in ["view", "change"]:
            permission = Permission.objects.get(
                content_type=content_type, codename=f"{action}_{model._meta.model_name}"
            )
            wagtail_group.permissions.add(permission)

    wagtail_group.save()
    return wagtail_group


@pytest.fixture
def wagtail_user(django_user_model, wagtail_user_group):
    username = "wagtail_user"
    password = "wagtail_password"
    wagtail_user = django_user_model.objects.create_user(
        username=username, password=password, is_superuser=False
    )
    wagtail_user.groups.add(wagtail_user_group)
    wagtail_user.save()
    return wagtail_user, password


@pytest.fixture
def wagtail_user_client(client, wagtail_user):
    user, plaintext_password = wagtail_user
    client.login(username=user.username, password=plaintext_password)
    return client
