from celery import shared_task

from io import StringIO

from django.core.management import call_command


@shared_task(bind=True, name="debug_task")
def debug_task(self):
    return "Task successfully run!"


@shared_task(bind=True, name="batch_extract")
def run_batch_extract(self):
    out = StringIO()
    call_command("batch_extract", stdout=out)

    if "SUCCESS" in out.getvalue():
        return "SUCCESS"
    else:
        return "FAILURE"
