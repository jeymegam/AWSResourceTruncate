"""KMS cleaner - schedules deletion of customer-managed KMS keys.

Respects exclusions defined in exclusions.py to protect keys used by
shared infrastructure (Lambda environment variable encryption, etc.).
"""

from cleaners.base import BaseCleaner
from exclusions import EXCLUDED_KMS_KEYS


class KMSCleaner(BaseCleaner):
    service_name = "kms"
    display_name = "KMS Keys"

    def clean(self):
        client = self.get_client()
        self._schedule_key_deletion(client)
        self._delete_aliases(client)

    def _schedule_key_deletion(self, client):
        """Schedule deletion of all customer-managed KMS keys (7-day minimum)."""
        paginator = client.get_paginator("list_keys")

        for page in paginator.paginate():
            for key in page.get("Keys", []):
                key_id = key["KeyId"]

                # Check if this key is excluded
                if key_id in EXCLUDED_KMS_KEYS:
                    self.log_skip("KMS Key", key_id, "excluded (shared infrastructure)")
                    continue

                try:
                    # Get key metadata to check if it's customer-managed
                    metadata = client.describe_key(KeyId=key_id)["KeyMetadata"]

                    # Skip AWS-managed keys and keys already pending deletion
                    if metadata["KeyManager"] != "CUSTOMER":
                        continue
                    if metadata["KeyState"] in ("PendingDeletion", "PendingImport"):
                        continue

                    # Disable the key first
                    if not self.dry_run:
                        client.disable_key(KeyId=key_id)
                        # Schedule deletion with minimum 7-day waiting period
                        client.schedule_key_deletion(
                            KeyId=key_id, PendingWindowInDays=7
                        )
                    self.log_delete(
                        "KMS Key (scheduled 7-day deletion)",
                        f"{key_id} ({metadata.get('Description', 'no description')})",
                    )

                except Exception as e:
                    self.log_error(f"Could not schedule deletion for key {key_id}", e)

    def _delete_aliases(self, client):
        """Delete all custom KMS aliases (not aws/ prefixed)."""
        paginator = client.get_paginator("list_aliases")

        for page in paginator.paginate():
            for alias in page.get("Aliases", []):
                alias_name = alias["AliasName"]

                # Skip AWS-managed aliases
                if alias_name.startswith("alias/aws/"):
                    continue

                # Skip aliases pointing to excluded keys
                target_key = alias.get("TargetKeyId", "")
                if target_key in EXCLUDED_KMS_KEYS:
                    self.log_skip(
                        "KMS Alias", alias_name, "points to excluded key"
                    )
                    continue

                try:
                    if not self.dry_run:
                        client.delete_alias(AliasName=alias_name)
                    self.log_delete("KMS Alias", alias_name)
                except Exception as e:
                    self.log_error(f"Could not delete alias {alias_name}", e)
