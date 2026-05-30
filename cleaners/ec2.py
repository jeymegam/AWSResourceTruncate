"""EC2 resource cleaner - instances, security groups, key pairs, EBS volumes, EIPs, NAT gateways."""

import time
from cleaners.base import BaseCleaner


class EC2Cleaner(BaseCleaner):
    service_name = "ec2"
    display_name = "EC2 Resources"

    def clean(self):
        client = self.get_client()
        self._terminate_instances(client)
        self._delete_nat_gateways(client)
        self._release_elastic_ips(client)
        self._delete_volumes(client)
        self._delete_snapshots(client)
        self._delete_security_groups(client)
        self._delete_key_pairs(client)
        self._delete_launch_templates(client)

    def _terminate_instances(self, client):
        """Terminate all EC2 instances."""
        paginator = client.get_paginator("describe_instances")
        instance_ids = []

        for page in paginator.paginate():
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    state = instance["State"]["Name"]
                    if state not in ("terminated", "shutting-down"):
                        instance_ids.append(instance["InstanceId"])

        if not instance_ids:
            self.logger.info("No running EC2 instances found.")
            return

        # Disable termination protection
        for iid in instance_ids:
            try:
                client.modify_instance_attribute(
                    InstanceId=iid,
                    DisableApiTermination={"Value": False},
                )
            except Exception:
                pass

        if not self.dry_run:
            client.terminate_instances(InstanceIds=instance_ids)
            self.logger.info(f"Terminating {len(instance_ids)} instances, waiting...")
            waiter = client.get_waiter("instance_terminated")
            waiter.wait(InstanceIds=instance_ids)

        for iid in instance_ids:
            self.log_delete("EC2 instance", iid)

    def _delete_nat_gateways(self, client):
        """Delete all NAT gateways."""
        paginator = client.get_paginator("describe_nat_gateways")
        for page in paginator.paginate(
            Filter=[{"Name": "state", "Values": ["available", "pending"]}]
        ):
            for nat in page["NatGateways"]:
                nat_id = nat["NatGatewayId"]
                if not self.dry_run:
                    client.delete_nat_gateway(NatGatewayId=nat_id)
                self.log_delete("NAT Gateway", nat_id)

    def _release_elastic_ips(self, client):
        """Release all Elastic IPs."""
        addresses = client.describe_addresses().get("Addresses", [])
        for addr in addresses:
            alloc_id = addr.get("AllocationId")
            if alloc_id:
                # Disassociate first if attached
                assoc_id = addr.get("AssociationId")
                if assoc_id and not self.dry_run:
                    client.disassociate_address(AssociationId=assoc_id)
                if not self.dry_run:
                    client.release_address(AllocationId=alloc_id)
                self.log_delete("Elastic IP", addr.get("PublicIp", alloc_id))

    def _delete_volumes(self, client):
        """Delete all available (unattached) EBS volumes."""
        paginator = client.get_paginator("describe_volumes")
        for page in paginator.paginate(
            Filters=[{"Name": "status", "Values": ["available"]}]
        ):
            for vol in page["Volumes"]:
                vol_id = vol["VolumeId"]
                if not self.dry_run:
                    client.delete_volume(VolumeId=vol_id)
                self.log_delete("EBS Volume", vol_id)

    def _delete_snapshots(self, client):
        """Delete all owned EBS snapshots."""
        account_id = self.get_client("sts").get_caller_identity()["Account"]
        paginator = client.get_paginator("describe_snapshots")
        for page in paginator.paginate(OwnerIds=[account_id]):
            for snap in page["Snapshots"]:
                snap_id = snap["SnapshotId"]
                if not self.dry_run:
                    try:
                        client.delete_snapshot(SnapshotId=snap_id)
                    except Exception as e:
                        self.log_error(f"Could not delete snapshot {snap_id}", e)
                        continue
                self.log_delete("EBS Snapshot", snap_id)

    def _delete_security_groups(self, client):
        """Delete all non-default security groups."""
        sgs = client.describe_security_groups().get("SecurityGroups", [])

        # First pass: revoke all ingress/egress rules referencing other SGs
        for sg in sgs:
            if sg["GroupName"] == "default":
                continue
            sg_id = sg["GroupId"]
            try:
                if sg.get("IpPermissions") and not self.dry_run:
                    client.revoke_security_group_ingress(
                        GroupId=sg_id, IpPermissions=sg["IpPermissions"]
                    )
                if sg.get("IpPermissionsEgress") and not self.dry_run:
                    client.revoke_security_group_egress(
                        GroupId=sg_id, IpPermissions=sg["IpPermissionsEgress"]
                    )
            except Exception:
                pass

        # Second pass: delete the groups
        for sg in sgs:
            if sg["GroupName"] == "default":
                continue
            sg_id = sg["GroupId"]
            if not self.dry_run:
                try:
                    client.delete_security_group(GroupId=sg_id)
                except Exception as e:
                    self.log_error(f"Could not delete SG {sg_id}", e)
                    continue
            self.log_delete("Security Group", f"{sg_id} ({sg['GroupName']})")

    def _delete_key_pairs(self, client):
        """Delete all key pairs."""
        key_pairs = client.describe_key_pairs().get("KeyPairs", [])
        for kp in key_pairs:
            kp_name = kp["KeyName"]
            if not self.dry_run:
                client.delete_key_pair(KeyName=kp_name)
            self.log_delete("Key Pair", kp_name)

    def _delete_launch_templates(self, client):
        """Delete all launch templates."""
        templates = client.describe_launch_templates().get("LaunchTemplates", [])
        for lt in templates:
            lt_id = lt["LaunchTemplateId"]
            if not self.dry_run:
                client.delete_launch_template(LaunchTemplateId=lt_id)
            self.log_delete("Launch Template", f"{lt_id} ({lt['LaunchTemplateName']})")
