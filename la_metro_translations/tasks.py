import logging

from io import StringIO
from celery import shared_task

from django.core.management import call_command


@shared_task(bind=True, name="debug_task")
def debug_task(self):
    return "Task successfully run!"


@shared_task(bind=True, name="batch_extract", soft_time_limit=21600)
def run_batch_extract(self):
    # Capture the logger output of batch_extract command
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger(
        "la_metro_translations.management.commands.batch_extract"
    )
    logger.addHandler(handler)

    try:
        call_command("batch_extract")
    finally:
        logger.removeHandler(handler)

    # Return logger output as task result data
    return log_stream.getvalue()
