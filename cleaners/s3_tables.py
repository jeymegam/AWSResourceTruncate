"""S3 Tables cleaner - deletes S3 table buckets, namespaces, and tables."""

from cleaners.base import BaseCleaner


class S3TablesCleaner(BaseCleaner):
    service_name = "s3tables"
    display_name = "S3 Tables"

    def clean(self):
        try:
            client = self.get_client()
        except Exception as e:
            self.logger.info(f"S3 Tables service not available in this region: {e}")
            return

        try:
            table_buckets = client.list_table_buckets().get("tableBuckets", [])
        except Exception as e:
            self.logger.info(f"S3 Tables not supported or no access: {e}")
            return

        if not table_buckets:
            self.logger.info("No S3 table buckets found.")
            return

        for tb in table_buckets:
            tb_arn = tb["arn"]
            tb_name = tb["name"]
            self._delete_table_bucket(client, tb_arn, tb_name)

    def _delete_table_bucket(self, client, tb_arn, tb_name):
        """Delete all tables, namespaces, then the table bucket itself."""
        try:
            # List and delete all namespaces and their tables
            namespaces = client.list_namespaces(tableBucketARN=tb_arn).get(
                "namespaces", []
            )
            for ns in namespaces:
                ns_name = ns["namespace"][0]
                self._delete_namespace_tables(client, tb_arn, ns_name)

                if not self.dry_run:
                    client.delete_namespace(tableBucketARN=tb_arn, namespace=ns_name)
                self.log_delete("S3 Table Namespace", f"{tb_name}/{ns_name}")

            # Delete the table bucket
            if not self.dry_run:
                client.delete_table_bucket(tableBucketARN=tb_arn)
            self.log_delete("S3 Table Bucket", tb_name)

        except Exception as e:
            self.log_error(f"Could not delete table bucket {tb_name}", e)

    def _delete_namespace_tables(self, client, tb_arn, ns_name):
        """Delete all tables in a namespace."""
        tables = client.list_tables(tableBucketARN=tb_arn, namespace=ns_name).get(
            "tables", []
        )
        for table in tables:
            table_name = table["name"]
            if not self.dry_run:
                client.delete_table(
                    tableBucketARN=tb_arn, namespace=ns_name, name=table_name
                )
            self.log_delete("S3 Table", f"{ns_name}.{table_name}")
