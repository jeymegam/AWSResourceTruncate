"""S3 Tables cleaner - deletes S3 table buckets, namespaces, tables, AND underlying data.

The S3 Tables API only removes table metadata. The actual data (Iceberg/Parquet files)
is stored in a backing S3 bucket that must be emptied separately.
"""

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

        # Clean up underlying S3 data buckets used by S3 Tables
        self._delete_table_data_buckets()

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

    def _delete_table_data_buckets(self):
        """Delete S3 buckets that store the underlying table data.

        S3 Tables stores actual data (Iceberg metadata + Parquet files) in
        backing S3 buckets. These typically have prefixes like:
        - s3tablescatalog-* (managed by S3 Tables service)
        - Buckets with 's3-tables' or 'table-bucket' in the name

        This method finds and empties those buckets.
        """
        s3_client = self.get_client("s3")
        s3_resource = self.get_resource("s3")

        # Patterns that identify S3 Tables data buckets
        table_data_prefixes = (
            "s3tablescatalog-",
            "s3-tables-",
            "table-bucket-",
        )

        try:
            buckets = s3_client.list_buckets().get("Buckets", [])
            for bucket in buckets:
                bucket_name = bucket["Name"]
                # Check if this is a table data bucket
                if any(bucket_name.startswith(p) for p in table_data_prefixes):
                    self._empty_and_delete_bucket(s3_client, s3_resource, bucket_name)
        except Exception as e:
            self.log_error("Could not clean S3 Tables data buckets", e)

    def _empty_and_delete_bucket(self, s3_client, s3_resource, bucket_name):
        """Empty all objects/versions and delete the bucket."""
        try:
            bucket = s3_resource.Bucket(bucket_name)
            if not self.dry_run:
                bucket.object_versions.all().delete()
                bucket.objects.all().delete()
                s3_client.delete_bucket(Bucket=bucket_name)
            self.log_delete("S3 Tables Data Bucket", bucket_name)
        except Exception as e:
            self.log_error(f"Could not delete table data bucket {bucket_name}", e)
