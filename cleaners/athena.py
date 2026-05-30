"""Athena cleaner - deletes workgroups and named queries."""

from cleaners.base import BaseCleaner


class AthenaCleaner(BaseCleaner):
    service_name = "athena"
    display_name = "Athena Resources"

    def clean(self):
        client = self.get_client()
        self._delete_named_queries(client)
        self._delete_workgroups(client)

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
