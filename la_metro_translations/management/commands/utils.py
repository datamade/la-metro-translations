from django.db import connections


class ConnManagerMixin:
    @staticmethod
    def reset_db_connections():
        """
        Close connections and allow Django to automatically reconnect.
        """
        for conn in connections.all():
            conn.close()
