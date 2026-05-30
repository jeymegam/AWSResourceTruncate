"""SNS cleaner - deletes all SNS topics and subscriptions."""

from cleaners.base import BaseCleaner


class SNSCleaner(BaseCleaner):
    service_name = "sns"
    display_name = "SNS Topics"

    def clean(self):
        client = self.get_client()
        self._delete_topics(client)

    def _delete_topics(self, client):
        """Delete all SNS topics and their subscriptions."""
        paginator = client.get_paginator("list_topics")
        found = False

        for page in paginator.paginate():
            for topic in page.get("Topics", []):
                found = True
                topic_arn = topic["TopicArn"]
                topic_name = topic_arn.split(":")[-1]

                try:
                    # Delete all subscriptions for this topic
                    sub_paginator = client.get_paginator("list_subscriptions_by_topic")
                    for sub_page in sub_paginator.paginate(TopicArn=topic_arn):
                        for sub in sub_page.get("Subscriptions", []):
                            sub_arn = sub["SubscriptionArn"]
                            if sub_arn != "PendingConfirmation" and not self.dry_run:
                                client.unsubscribe(SubscriptionArn=sub_arn)

                    if not self.dry_run:
                        client.delete_topic(TopicArn=topic_arn)
                    self.log_delete("SNS Topic", topic_name)

                except Exception as e:
                    self.log_error(f"Could not delete topic {topic_name}", e)

        if not found:
            self.logger.info("No SNS topics found.")
