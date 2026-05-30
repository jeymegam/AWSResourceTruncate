"""Athena cleaner - deletes workgroups, named queries, AND query result output files.

Athena stores query results in S3 (default: aws-athena-query-results-* buckets
or custom output locations configured per workgroup). This cleaner empties those
output locations as well.
"""

from cleaners.base import BaseCleaner


class AthenaCleaner(BaseCleaner):
    service_name = "athena"
    display_name = "Athena Resources"

    def clean(self):
        client = self.get_client()
        self._clean_query_results(client)
        self._delete_named_queries(client)
        self._delete_workgroups(client)
        self._delete_athena_result_buckets()

    def _clean_query_results(self, client):
        """Delete query result files from each workgroup's output location."""
        try:
            workgroups = client.list_work_groups().get("WorkGroups", [])
            cleaned_locations = set()

            for wg in workgroups:
                wg_name = wg["Name"]
                try:
                    wg_config = client.get_work_group(WorkGroup=wg_name)
                    output_location = (
                        wg_config.get("WorkGroup", {})
                        .get("Configuration", {})
                        .get("ResultConfiguration", {})
                        .get("OutputLocation", "")
                    )

                    if output_location and output_location not in cleaned_locations:
                        cleaned_locations.add(output_location)
                        self._empty_s3_location(output_location, wg_name)

                except Exception as e:
                    self.log_error(
                        f"Could not get output location for workgroup {wg_name}", e
                    )

        except Exception as e:
            self.log_error("Could not list workgroups for result cleanup", e)

    def _empty_s3_location(self, s3_uri, workgroup_name):
        """Empty all objects at an S3 URI (s3://bucket/prefix)."""
        if not s3_uri.startswith("s3://"):
            return

        # Parse s3://bucket/prefix
        path = s3_uri[5:]  # Remove 's3://'
        parts = path.split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""

        try:
            s3_resource = self.get_resource("s3")
            bucket = s3_resource.Bucket(bucket_name)

            if prefix:
                objects = bucket.objects.filter(Prefix=prefix)
            else:
                objects = bucket.objects.all()

            # Count objects for logging
            obj_list = list(objects)
            if not obj_list:
                return

            if not self.dry_run:
                # Delete in batches of 1000 (S3 API limit)
                for i in range(0, len(obj_list), 1000):
                    batch = obj_list[i : i + 1000]
                    bucket.delete_objects(
                        Delete={"Objects": [{"Key": obj.key} for obj in batch]}
                    )

                # Also delete any versioned objects
                if prefix:
                    versions = bucket.object_versions.filter(Prefix=prefix)
                else:
                    versions = bucket.object_versions.all()
                version_list = list(versions)
                if version_list:
                    for i in range(0, len(version_list), 1000):
                        batch = version_list[i : i + 1000]
                        bucket.delete_objects(
                            Delete={
                                "Objects": [
                                    {"Key": v.object_key, "VersionId": v.id}
                                    for v in batch
                                ]
                            }
                        )

            self.log_delete(
                "Athena Query Results",
                f"{len(obj_list)} objects at {s3_uri} (workgroup: {workgroup_name})",
            )

        except Exception as e:
            self.log_error(f"Could not empty Athena results at {s3_uri}", e)

    def _delete_athena_result_buckets(self):
        """Find and empty S3 buckets matching the default Athena results pattern."""
        try:
            s3_client = self.get_client("s3")
            s3_resource = self.get_resource("s3")

            buckets = s3_client.list_buckets().get("Buckets", [])
            for bucket in buckets:
                bucket_name = bucket["Name"]
                # Default Athena result bucket naming patterns
                if (
                    bucket_name.startswith("aws-athena-query-results")
                    or bucket_name.startswith("athena-results")
                    or "athena-output" in bucket_name
                    or "athena-query" in bucket_name
                ):
                    self._empty_and_delete_result_bucket(
                        s3_client, s3_resource, bucket_name
                    )

        except Exception as e:
            self.log_error("Could not clean Athena result buckets", e)

    def _empty_and_delete_result_bucket(self, s3_client, s3_resource, bucket_name):
        """Empty and delete an Athena results bucket."""
        try:
            bucket = s3_resource.Bucket(bucket_name)
            if not self.dry_run:
                bucket.object_versions.all().delete()
                bucket.objects.all().delete()
                s3_client.delete_bucket(Bucket=bucket_name)
            self.log_delete("Athena Results Bucket", bucket_name)
        except Exception as e:
            self.log_error(f"Could not delete Athena results bucket {bucket_name}", e)

    def _delete_named_queries(self, client):
        """Delete all Athena named queries."""
        try:
            paginator = client.get_paginator("list_named_queries")
            for page in paginator.paginate():
                for query_id in page.get("NamedQueryIds", []):
                    if not self.dry_run:
                        client.delete_named_query(NamedQueryId=query_id)
                    self.log_delete("Athena Named Query", query_id)
        except Exception as e:
            self.log_error("Could not delete named queries", e)

    def _delete_workgroups(self, client):
        """Delete all non-primary Athena workgroups."""
        try:
            workgroups = client.list_work_groups().get("WorkGroups", [])
            for wg in workgroups:
                wg_name = wg["Name"]
                if wg_name == "primary":
                    self.log_skip("Athena Workgroup", wg_name, "primary workgroup")
                    continue
                if not self.dry_run:
                    client.delete_work_group(
                        WorkGroup=wg_name, RecursiveDeleteOption=True
                    )
                self.log_delete("Athena Workgroup", wg_name)
        except Exception as e:
            self.log_error("Could not delete workgroups", e)
