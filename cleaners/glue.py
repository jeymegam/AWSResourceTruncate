"""Glue cleaner - deletes databases, tables, crawlers, and jobs."""

from cleaners.base import BaseCleaner


class GlueCleaner(BaseCleaner):
    service_name = "glue"
    display_name = "Glue Resources"

    def clean(self):
        client = self.get_client()
        self._delete_jobs(client)
        self._delete_crawlers(client)
        self._delete_databases(client)

    def _delete_jobs(self, client):
        """Delete all Glue jobs."""
        try:
            paginator = client.get_paginator("get_jobs")
            for page in paginator.paginate():
                for job in page.get("Jobs", []):
                    job_name = job["Name"]
                    if not self.dry_run:
                        client.delete_job(JobName=job_name)
                    self.log_delete("Glue Job", job_name)
        except Exception as e:
            self.log_error("Could not list/delete Glue jobs", e)

    def _delete_crawlers(self, client):
        """Delete all Glue crawlers."""
        try:
            paginator = client.get_paginator("get_crawlers")
            for page in paginator.paginate():
                for crawler in page.get("Crawlers", []):
                    crawler_name = crawler["Name"]
                    # Stop crawler if running
                    if crawler.get("State") == "RUNNING":
                        if not self.dry_run:
                            client.stop_crawler(Name=crawler_name)
                    if not self.dry_run:
                        client.delete_crawler(Name=crawler_name)
                    self.log_delete("Glue Crawler", crawler_name)
        except Exception as e:
            self.log_error("Could not list/delete Glue crawlers", e)

    def _delete_databases(self, client):
        """Delete all Glue databases and their tables."""
        try:
            paginator = client.get_paginator("get_databases")
            for page in paginator.paginate():
                for db in page.get("DatabaseList", []):
                    db_name = db["Name"]
                    # Skip the default database
                    if db_name == "default":
                        self.log_skip("Glue Database", db_name, "default database")
                        continue
                    self._delete_database_tables(client, db_name)
                    if not self.dry_run:
                        client.delete_database(Name=db_name)
                    self.log_delete("Glue Database", db_name)
        except Exception as e:
            self.log_error("Could not list/delete Glue databases", e)

    def _delete_database_tables(self, client, db_name):
        """Delete all tables in a Glue database."""
        try:
            paginator = client.get_paginator("get_tables")
            for page in paginator.paginate(DatabaseName=db_name):
                for table in page.get("TableList", []):
                    table_name = table["Name"]
                    if not self.dry_run:
                        client.delete_table(DatabaseName=db_name, Name=table_name)
                    self.log_delete("Glue Table", f"{db_name}.{table_name}")
        except Exception as e:
            self.log_error(f"Could not delete tables in {db_name}", e)
