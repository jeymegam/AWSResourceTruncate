"""IAM cleaner - deletes roles, policies, users, and instance profiles."""

from cleaners.base import BaseCleaner

# Prefixes for AWS-managed roles that should never be deleted
PROTECTED_PREFIXES = (
    "AWS",
    "aws-",
    "AWSServiceRole",
    "OrganizationAccountAccessRole",
)


class IAMCleaner(BaseCleaner):
    service_name = "iam"
    display_name = "IAM Resources"

    def clean(self):
        client = self.get_client()
        self._delete_roles(client)
        self._delete_policies(client)
        self._delete_users(client)
        self._delete_instance_profiles(client)

    def _is_protected(self, name):
        """Check if a role/resource name is AWS-managed and should be skipped."""
        return any(name.startswith(prefix) for prefix in PROTECTED_PREFIXES)

    def _delete_roles(self, client):
        """Delete all non-AWS-managed IAM roles."""
        paginator = client.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                role_name = role["RoleName"]
                if self._is_protected(role_name):
                    self.log_skip("IAM Role", role_name, "AWS-managed")
                    continue
                # Check if it's a service-linked role
                if role.get("Path", "").startswith("/aws-service-role/"):
                    self.log_skip("IAM Role", role_name, "service-linked role")
                    continue
                self._delete_single_role(client, role_name)

    def _delete_single_role(self, client, role_name):
        """Fully detach and delete a single IAM role."""
        try:
            # Detach managed policies
            attached = client.list_attached_role_policies(RoleName=role_name).get(
                "AttachedPolicies", []
            )
            for policy in attached:
                if not self.dry_run:
                    client.detach_role_policy(
                        RoleName=role_name, PolicyArn=policy["PolicyArn"]
                    )

            # Delete inline policies
            inline = client.list_role_policies(RoleName=role_name).get(
                "PolicyNames", []
            )
            for policy_name in inline:
                if not self.dry_run:
                    client.delete_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )

            # Remove from instance profiles
            profiles = client.list_instance_profiles_for_role(
                RoleName=role_name
            ).get("InstanceProfiles", [])
            for profile in profiles:
                if not self.dry_run:
                    client.remove_role_from_instance_profile(
                        InstanceProfileName=profile["InstanceProfileName"],
                        RoleName=role_name,
                    )

            if not self.dry_run:
                client.delete_role(RoleName=role_name)
            self.log_delete("IAM Role", role_name)

        except Exception as e:
            self.log_error(f"Could not delete role {role_name}", e)

    def _delete_policies(self, client):
        """Delete all customer-managed IAM policies."""
        paginator = client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for policy in page["Policies"]:
                policy_arn = policy["Arn"]
                policy_name = policy["PolicyName"]
                try:
                    # Detach from all entities
                    entities = client.list_entities_for_policy(PolicyArn=policy_arn)
                    for role in entities.get("PolicyRoles", []):
                        if not self.dry_run:
                            client.detach_role_policy(
                                RoleName=role["RoleName"], PolicyArn=policy_arn
                            )
                    for user in entities.get("PolicyUsers", []):
                        if not self.dry_run:
                            client.detach_user_policy(
                                UserName=user["UserName"], PolicyArn=policy_arn
                            )
                    for group in entities.get("PolicyGroups", []):
                        if not self.dry_run:
                            client.detach_group_policy(
                                GroupName=group["GroupName"], PolicyArn=policy_arn
                            )

                    # Delete non-default versions
                    versions = client.list_policy_versions(PolicyArn=policy_arn).get(
                        "Versions", []
                    )
                    for ver in versions:
                        if not ver["IsDefaultVersion"] and not self.dry_run:
                            client.delete_policy_version(
                                PolicyArn=policy_arn, VersionId=ver["VersionId"]
                            )

                    if not self.dry_run:
                        client.delete_policy(PolicyArn=policy_arn)
                    self.log_delete("IAM Policy", policy_name)

                except Exception as e:
                    self.log_error(f"Could not delete policy {policy_name}", e)

    def _delete_users(self, client):
        """Delete all IAM users (except the current caller)."""
        sts = self.get_client("sts")
        current_arn = sts.get_caller_identity()["Arn"]

        paginator = client.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                user_name = user["UserName"]
                # Don't delete the user running this script
                if user_name in current_arn:
                    self.log_skip("IAM User", user_name, "current caller")
                    continue
                self._delete_single_user(client, user_name)

    def _delete_single_user(self, client, user_name):
        """Fully clean up and delete a single IAM user."""
        try:
            # Delete access keys
            keys = client.list_access_keys(UserName=user_name).get(
                "AccessKeyMetadata", []
            )
            for key in keys:
                if not self.dry_run:
                    client.delete_access_key(
                        UserName=user_name, AccessKeyId=key["AccessKeyId"]
                    )

            # Delete login profile
            try:
                if not self.dry_run:
                    client.delete_login_profile(UserName=user_name)
            except client.exceptions.NoSuchEntityException:
                pass

            # Detach policies
            attached = client.list_attached_user_policies(UserName=user_name).get(
                "AttachedPolicies", []
            )
            for policy in attached:
                if not self.dry_run:
                    client.detach_user_policy(
                        UserName=user_name, PolicyArn=policy["PolicyArn"]
                    )

            # Delete inline policies
            inline = client.list_user_policies(UserName=user_name).get(
                "PolicyNames", []
            )
            for policy_name in inline:
                if not self.dry_run:
                    client.delete_user_policy(
                        UserName=user_name, PolicyName=policy_name
                    )

            # Remove from groups
            groups = client.list_groups_for_user(UserName=user_name).get("Groups", [])
            for group in groups:
                if not self.dry_run:
                    client.remove_user_from_group(
                        GroupName=group["GroupName"], UserName=user_name
                    )

            # Delete MFA devices
            mfas = client.list_mfa_devices(UserName=user_name).get("MFADevices", [])
            for mfa in mfas:
                if not self.dry_run:
                    client.deactivate_mfa_device(
                        UserName=user_name, SerialNumber=mfa["SerialNumber"]
                    )
                    client.delete_virtual_mfa_device(SerialNumber=mfa["SerialNumber"])

            if not self.dry_run:
                client.delete_user(UserName=user_name)
            self.log_delete("IAM User", user_name)

        except Exception as e:
            self.log_error(f"Could not delete user {user_name}", e)

    def _delete_instance_profiles(self, client):
        """Delete all instance profiles."""
        paginator = client.get_paginator("list_instance_profiles")
        for page in paginator.paginate():
            for profile in page["InstanceProfiles"]:
                profile_name = profile["InstanceProfileName"]
                if self._is_protected(profile_name):
                    continue
                try:
                    # Remove all roles first
                    for role in profile.get("Roles", []):
                        if not self.dry_run:
                            client.remove_role_from_instance_profile(
                                InstanceProfileName=profile_name,
                                RoleName=role["RoleName"],
                            )
                    if not self.dry_run:
                        client.delete_instance_profile(
                            InstanceProfileName=profile_name
                        )
                    self.log_delete("Instance Profile", profile_name)
                except Exception as e:
                    self.log_error(
                        f"Could not delete instance profile {profile_name}", e
                    )
