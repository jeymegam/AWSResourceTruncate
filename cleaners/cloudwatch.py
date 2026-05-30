"""CloudWatch cleaner - deletes log groups, alarms, and dashboards."""

from cleaners.base import BaseCleaner


class CloudWatchCleaner(BaseCleaner):
    service_name = "logs"
    display_name = "CloudWatch Resources"

    def clean(self):
        self._delete_log_groups()
        self._delete_alarms()
        self._delete_dashboards()

    def _delete_log_groups(self):
        """Delete all CloudWatch log groups."""
        client = self.get_client("logs")
        paginator = client.get_paginator("describe_log_groups")
        found = False

        for page in paginator.paginate():
            for lg in page.get("logGroups", []):
                found = True
                lg_name = lg["logGroupName"]
                try:
                    if not self.dry_run:
                        client.delete_log_group(logGroupName=lg_name)
                    self.log_delete("Log Group", lg_name)
                except Exception as e:
                    self.log_error(f"Could not delete log group {lg_name}", e)

        if not found:
            self.logger.info("No CloudWatch log groups found.")

    def _delete_alarms(self):
        """Delete all CloudWatch alarms."""
        client = self.get_client("cloudwatch")
        paginator = client.get_paginator("describe_alarms")
        alarm_names = []

        for page in paginator.paginate():
            for alarm in page.get("MetricAlarms", []):
                alarm_names.append(alarm["AlarmName"])
            for alarm in page.get("CompositeAlarms", []):
                alarm_names.append(alarm["AlarmName"])

        if not alarm_names:
            self.logger.info("No CloudWatch alarms found.")
            return

        # Delete in batches of 100 (API limit)
        for i in range(0, len(alarm_names), 100):
            batch = alarm_names[i : i + 100]
            if not self.dry_run:
                client.delete_alarms(AlarmNames=batch)
            for name in batch:
                self.log_delete("CloudWatch Alarm", name)

    def _delete_dashboards(self):
        """Delete all CloudWatch dashboards."""
        client = self.get_client("cloudwatch")
        dashboards = client.list_dashboards().get("DashboardEntries", [])

        if not dashboards:
            self.logger.info("No CloudWatch dashboards found.")
            return

        for dash in dashboards:
            dash_name = dash["DashboardName"]
            if not self.dry_run:
                client.delete_dashboards(DashboardNames=[dash_name])
            self.log_delete("CloudWatch Dashboard", dash_name)
