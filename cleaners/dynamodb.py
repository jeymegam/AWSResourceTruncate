"""DynamoDB cleaner - deletes all DynamoDB tables."""

from cleaners.base import BaseCleaner


class DynamoDBCleaner(BaseCleaner):
    service_name = "dynamodb"
    display_name = "DynamoDB Tables"

    def clean(self):
        client = self.get_client()
        paginator = client.get_paginator("list_tables")

        table_names = []
        for page in paginator.paginate():
            table_names.extend(page.get("TableNames", []))

        if not table_names:
            self.logger.info("No DynamoDB tables found.")
            return

        for table_name in table_names:
            self._delete_table(client, table_name)

    def _delete_table(self, client, table_name):
        """Delete a single DynamoDB table."""
        try:
            # Check if table has deletion protection
            desc = client.describe_table(TableName=table_name)["Table"]
            if desc.get("DeletionProtectionEnabled"):
                if not self.dry_run:
                    client.update_table(
                        TableName=table_name, DeletionProtectionEnabled=False
                    )
                self.logger.info(
                    f"Disabled deletion protection on table: {table_name}"
                )

            if not self.dry_run:
                client.delete_table(TableName=table_name)
            self.log_delete("DynamoDB Table", table_name)

        except Exception as e:
            self.log_error(f"Could not delete table {table_name}", e)
