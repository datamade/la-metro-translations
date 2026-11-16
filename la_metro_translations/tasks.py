from celery import shared_task

from io import StringIO

from django.core.management import call_command


@shared_task(bind=True, name="debug_task")
def debug_task(self):
    return "Task successfully run!"


@shared_task(bind=True, name="batch_extract", soft_time_limit=21600)
def run_batch_extract(self):
    out = StringIO()

    try:
        call_command("batch_extract", stdout=out)
    finally:
        # Pipe management command logger output to the task result
        return out.getvalue()
