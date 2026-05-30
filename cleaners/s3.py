"""S3 bucket cleaner - empties and deletes all S3 buckets."""

from cleaners.base import BaseCleaner


class S3Cleaner(BaseCleaner):
    service_name = "s3"
    display_name = "S3 Buckets"

    def clean(self):
        client = self.get_client()
        s3_resource = self.get_resource()

        buckets = client.list_buckets().get("Buckets", [])
        if not buckets:
            self.logger.info("No S3 buckets found.")
            return

        for bucket in buckets:
            bucket_name = bucket["Name"]
            self._delete_bucket(client, s3_resource, bucket_name)

    def _delete_bucket(self, client, s3_resource, bucket_name):
        """Empty and delete a single S3 bucket."""
        try:
            bucket = s3_resource.Bucket(bucket_name)

            if not self.dry_run:
                # Delete all object versions (handles versioned buckets)
                bucket.object_versions.all().delete()
                # Delete any remaining objects
                bucket.objects.all().delete()
                # Remove bucket policy to avoid access denied on delete
                try:
                    client.delete_bucket_policy(Bucket=bucket_name)
                except Exception:
                    pass
                # Delete the bucket
                client.delete_bucket(Bucket=bucket_name)

            self.log_delete("S3 Bucket", bucket_name)

        except Exception as e:
            self.log_error(f"Could not delete bucket {bucket_name}", e)
