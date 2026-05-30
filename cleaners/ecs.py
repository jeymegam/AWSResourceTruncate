"""ECS cleaner - deletes clusters, services, and task definitions."""

from cleaners.base import BaseCleaner


class ECSCleaner(BaseCleaner):
    service_name = "ecs"
    display_name = "ECS Resources"

    def clean(self):
        client = self.get_client()
        self._delete_clusters(client)
        self._deregister_task_definitions(client)

    def _delete_clusters(self, client):
        """Delete all ECS clusters and their services/tasks."""
        cluster_arns = client.list_clusters().get("clusterArns", [])

        if not cluster_arns:
            self.logger.info("No ECS clusters found.")
            return

        for cluster_arn in cluster_arns:
            cluster_name = cluster_arn.split("/")[-1]
            self._delete_cluster_resources(client, cluster_arn, cluster_name)

    def _delete_cluster_resources(self, client, cluster_arn, cluster_name):
        """Delete all services and tasks in a cluster, then delete the cluster."""
        try:
            # Stop all running tasks
            task_arns = client.list_tasks(
                cluster=cluster_arn, desiredStatus="RUNNING"
            ).get("taskArns", [])
            for task_arn in task_arns:
                if not self.dry_run:
                    client.stop_task(cluster=cluster_arn, task=task_arn)
                self.log_delete("ECS Task", task_arn.split("/")[-1])

            # Delete all services
            service_arns = client.list_services(cluster=cluster_arn).get(
                "serviceArns", []
            )
            for service_arn in service_arns:
                service_name = service_arn.split("/")[-1]
                if not self.dry_run:
                    # Scale down to 0 first
                    client.update_service(
                        cluster=cluster_arn,
                        service=service_arn,
                        desiredCount=0,
                    )
                    client.delete_service(
                        cluster=cluster_arn, service=service_arn, force=True
                    )
                self.log_delete("ECS Service", service_name)

            # Delete the cluster
            if not self.dry_run:
                client.delete_cluster(cluster=cluster_arn)
            self.log_delete("ECS Cluster", cluster_name)

        except Exception as e:
            self.log_error(f"Could not delete cluster {cluster_name}", e)

    def _deregister_task_definitions(self, client):
        """Deregister all task definitions."""
        try:
            paginator = client.get_paginator("list_task_definitions")
            for page in paginator.paginate(status="ACTIVE"):
                for td_arn in page.get("taskDefinitionArns", []):
                    if not self.dry_run:
                        client.deregister_task_definition(taskDefinition=td_arn)
                    self.log_delete("ECS Task Definition", td_arn.split("/")[-1])
        except Exception as e:
            self.log_error("Could not deregister task definitions", e)
