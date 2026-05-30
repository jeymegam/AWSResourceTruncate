"""SQS cleaner - deletes all SQS queues."""

from cleaners.base import BaseCleaner


class SQSCleaner(BaseCleaner):
    service_name = "sqs"
    display_name = "SQS Queues"

    def clean(self):
        client = self.get_client()
        self._delete_queues(client)

    def _delete_queues(self, client):
        """Delete all SQS queues."""
        try:
            paginator = client.get_paginator("list_queues")
            found = False

            for page in paginator.paginate():
                for queue_url in page.get("QueueUrls", []):
                    found = True
                    queue_name = queue_url.split("/")[-1]
                    try:
                        if not self.dry_run:
                            client.delete_queue(QueueUrl=queue_url)
                        self.log_delete("SQS Queue", queue_name)
                    except Exception as e:
                        self.log_error(f"Could not delete queue {queue_name}", e)

            if not found:
                self.logger.info("No SQS queues found.")

        except Exception as e:
            self.log_error("Could not list SQS queues", e)
