import json
import time
import logging

from typing import List
from io import StringIO
from datetime import datetime
import httpx

from mistralai import Mistral
from mistralai.models.batchjobout import BatchJobOut

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE_BYTES = 30_000_000  # 30MB Mistral batch API limit


class BatchUtils:
    @staticmethod
    def start_batch_job(
        client: Mistral,
        entries: List[dict],
        model: str,
        endpoint: str,
        timeout_hours: int,
    ) -> BatchJobOut:
        """
        Upload a batch file, then create and start the job. Returns the created job.
        """
        # Create batch file
        batch_file = StringIO()
        service = "ocr" if "ocr" in model else "translate"
        for entry in entries:
            batch_file.write(json.dumps(entry) + "\n")

        # Upload batch file
        batch_name = datetime.now().strftime(f"{service}_batch__%Y-%m-%d__%H-%M")
        batch_data = client.files.upload(
            file={
                "file_name": f"{batch_name}.jsonl",
                "content": batch_file.getvalue(),
            },
            purpose="batch",
        )
        batch_file.close()

        # Create and start batch job
        created_job = client.batch.jobs.create(
            input_files=[batch_data.id],
            model=model,
            endpoint=endpoint,
            timeout_hours=timeout_hours,
        )

        return created_job

    @staticmethod
    def check_batch_job(
        client: Mistral, job_id: str, timeout_hours: int, check_interval: int = 60
    ) -> httpx.Response | None:
        """
        Regularly checks a batch job until it is finished, reporting current progress
        each time a check is performed. Upon success, returns the downloaded output
        file. The interval for checking is defined in seconds.
        """
        start_time = time.time()
        minutes_elapsed = 0
        retrieved_job = client.batch.jobs.get(job_id=job_id)

        logger.info(
            "Batch job created! It will be checked every "
            f"{check_interval} seconds until complete..."
        )

        while retrieved_job.status in ["QUEUED", "RUNNING"]:
            time.sleep(check_interval)
            retrieved_job = client.batch.jobs.get(job_id=job_id)
            total_reqs = retrieved_job.total_requests
            succeeded_reqs = retrieved_job.succeeded_requests
            failed_reqs = retrieved_job.failed_requests

            logger.info(f"Status: {retrieved_job.status}")
            logger.info(f"Successful requests: {succeeded_reqs} out of {total_reqs}")
            logger.info(f"Failed requests: {failed_reqs} out of {total_reqs}")
            logger.info(
                "Percent done: "
                f"{round((succeeded_reqs + failed_reqs) / total_reqs, 1) * 100}%"
            )
            minutes_elapsed = round((time.time() - start_time) / 60, 1)

            if retrieved_job.status in ["QUEUED", "RUNNING"]:
                logger.info(f"Time elapsed: {minutes_elapsed} minutes...")
                logger.info("=======")

        # Check response for issues
        if retrieved_job.errors:
            logger.error(f"Errors: {retrieved_job.errors}")

        if retrieved_job.status == "TIMEOUT_EXCEEDED":
            logger.error(
                f"Batch job exceeded timeout of {timeout_hours} hours. "
                f"Job ID: {job_id}"
            )
            return
        elif retrieved_job.status != "SUCCESS" or not retrieved_job.output_file:
            logger.error(
                f"Batch job has stopped without an output file. "
                f"Status: {retrieved_job.status}; "
                f"Job ID: {job_id}"
            )
            return

        logger.info("Downloading file(s)...")
        response = client.files.download(file_id=retrieved_job.output_file)
        logger.info(f"--- Batch job finished in {minutes_elapsed} minutes. ---")
        return response
