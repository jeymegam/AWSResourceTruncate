"""RDS cleaner - deletes DB instances, clusters, and snapshots."""

from cleaners.base import BaseCleaner


class RDSCleaner(BaseCleaner):
    service_name = "rds"
    display_name = "RDS Resources"

    def clean(self):
        client = self.get_client()
        self._delete_instances(client)
        self._delete_clusters(client)
        self._delete_snapshots(client)
        self._delete_subnet_groups(client)

    def _delete_instances(self, client):
        """Delete all RDS instances."""
        paginator = client.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                db_id = db["DBInstanceIdentifier"]
                try:
                    # Disable deletion protection
                    if db.get("DeletionProtection") and not self.dry_run:
                        client.modify_db_instance(
                            DBInstanceIdentifier=db_id, DeletionProtection=False
                        )
                    if not self.dry_run:
                        client.delete_db_instance(
                            DBInstanceIdentifier=db_id,
                            SkipFinalSnapshot=True,
                            DeleteAutomatedBackups=True,
                        )
                    self.log_delete("RDS Instance", db_id)
                except Exception as e:
                    self.log_error(f"Could not delete RDS instance {db_id}", e)

    def _delete_clusters(self, client):
        """Delete all RDS/Aurora clusters."""
        paginator = client.get_paginator("describe_db_clusters")
        for page in paginator.paginate():
            for cluster in page.get("DBClusters", []):
                cluster_id = cluster["DBClusterIdentifier"]
                try:
                    if cluster.get("DeletionProtection") and not self.dry_run:
                        client.modify_db_cluster(
                            DBClusterIdentifier=cluster_id, DeletionProtection=False
                        )
                    if not self.dry_run:
                        client.delete_db_cluster(
                            DBClusterIdentifier=cluster_id, SkipFinalSnapshot=True
                        )
                    self.log_delete("RDS Cluster", cluster_id)
                except Exception as e:
                    self.log_error(f"Could not delete RDS cluster {cluster_id}", e)

    def _delete_snapshots(self, client):
        """Delete all manual RDS snapshots."""
        paginator = client.get_paginator("describe_db_snapshots")
        for page in paginator.paginate(SnapshotType="manual"):
            for snap in page.get("DBSnapshots", []):
                snap_id = snap["DBSnapshotIdentifier"]
                try:
                    if not self.dry_run:
                        client.delete_db_snapshot(DBSnapshotIdentifier=snap_id)
                    self.log_delete("RDS Snapshot", snap_id)
                except Exception as e:
                    self.log_error(f"Could not delete RDS snapshot {snap_id}", e)

    def _delete_subnet_groups(self, client):
        """Delete all DB subnet groups."""
        try:
            paginator = client.get_paginator("describe_db_subnet_groups")
            for page in paginator.paginate():
                for group in page.get("DBSubnetGroups", []):
                    group_name = group["DBSubnetGroupName"]
                    if group_name == "default":
                        continue
                    try:
                        if not self.dry_run:
                            client.delete_db_subnet_group(
                                DBSubnetGroupName=group_name
                            )
                        self.log_delete("DB Subnet Group", group_name)
                    except Exception as e:
                        self.log_error(
                            f"Could not delete subnet group {group_name}", e
                        )
        except Exception as e:
            self.log_error("Could not list DB subnet groups", e)
