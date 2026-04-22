from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from la_metro_translations.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """
    Process a single document
    """

    class Meta:
        model = Document
        fields = [
            "title",
            "source_url",
            "created_at",
            "updated_at",
            "document_type",
            "document_id",
            "entity_type",
            "entity_id",
            "entity_slug",
        ]

    def get_validators(self):
        # Turn off the unique constraint validator here
        # in order to let bulk_create's update_conflicts flag to work properly
        return [
            v
            for v in super().get_validators()
            if not isinstance(v, UniqueTogetherValidator)
        ]


class NotificationSerializer(serializers.Serializer):
    """
    Check that the api_key is correct, and process multiple documents
    """

    api_key = serializers.CharField(max_length=36)
    documents = DocumentSerializer(many=True)

    def validate_api_key(self, value):
        """
        Check api_key authorization
        """

        if value != settings.BOARDAGENDAS_API_KEY:
            raise serializers.ValidationError(
                "Unauthorized: Invalid api key. Double check the key submitted."
            )
        return value
