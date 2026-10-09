import shlex
import threading

import requests
from django.conf import settings
from django.core.management import call_command


class LocalBackend:
    def start_job(self, command, *args, **kwargs):
        thread = threading.Thread(
            target=call_command,
            args=(command, *args),
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()


class HerokuBackend:
    def start_job(self, command, *args, **kwargs):
        cmd_parts = ["python", "manage.py", command]
        for arg in args:
            cmd_parts.append(shlex.quote(str(arg)))
        for key, value in kwargs.items():
            if value is not None:
                cmd_parts.append(f"--{key}={value}")

        # For Heroku Platform dyno creation API reference, see:
        # https://devcenter.heroku.com/articles/platform-api-reference#dyno-create
        url = f"https://api.heroku.com/apps/{settings.HEROKU_APP_NAME}/dynos"
        response = requests.post(
            url,
            json={
                "command": " ".join(cmd_parts),
                "attach": False,
                "type": "run",
            },
            headers={
                "Accept": "application/vnd.heroku+json; version=3",
                "Authorization": f"Bearer {settings.HEROKU_API_TOKEN}",
            },
        )
        response.raise_for_status()
        return response.json().get("id")


def get_backend():
    return (
        HerokuBackend()
        if getattr(settings, "HEROKU_APP_NAME", None)
        and getattr(settings, "HEROKU_API_TOKEN", None)
        else LocalBackend()
    )
