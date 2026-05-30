"""CloudFormation cleaner - deletes all stacks."""

import time
from cleaners.base import BaseCleaner


class CloudFormationCleaner(BaseCleaner):
    service_name = "cloudformation"
    display_name = "CloudFormation Stacks"

    def clean(self):
        client = self.get_client()
        self._delete_stacks(client)

    def _delete_stacks(self, client):
        """Delete all CloudFormation stacks (non-nested, non-deleted)."""
        paginator = client.get_paginator("list_stacks")
        active_statuses = [
            "CREATE_COMPLETE",
            "UPDATE_COMPLETE",
            "ROLLBACK_COMPLETE",
            "UPDATE_ROLLBACK_COMPLETE",
            "CREATE_FAILED",
            "DELETE_FAILED",
            "IMPORT_COMPLETE",
            "IMPORT_ROLLBACK_COMPLETE",
        ]

        stacks_to_delete = []
        for page in paginator.paginate(StackStatusFilter=active_statuses):
            for stack in page.get("StackSummaries", []):
                # Skip nested stacks (they'll be deleted with parent)
                if stack.get("ParentId"):
                    continue
                stacks_to_delete.append(stack["StackName"])

        if not stacks_to_delete:
            self.logger.info("No CloudFormation stacks found.")
            return

        for stack_name in stacks_to_delete:
            self._delete_single_stack(client, stack_name)

    def _delete_single_stack(self, client, stack_name):
        """Delete a single CloudFormation stack with termination protection handling."""
        try:
            # Disable termination protection
            try:
                client.update_termination_protection(
                    EnableTerminationProtection=False, StackName=stack_name
                )
            except Exception:
                pass

            if not self.dry_run:
                client.delete_stack(StackName=stack_name)
                # Wait for deletion
                self.logger.info(f"Waiting for stack {stack_name} to delete...")
                waiter = client.get_waiter("stack_delete_complete")
                try:
                    waiter.wait(
                        StackName=stack_name,
                        WaiterConfig={"Delay": 10, "MaxAttempts": 60},
                    )
                except Exception as e:
                    self.log_error(
                        f"Stack {stack_name} deletion may still be in progress", e
                    )

            self.log_delete("CloudFormation Stack", stack_name)

        except Exception as e:
            self.log_error(f"Could not delete stack {stack_name}", e)
