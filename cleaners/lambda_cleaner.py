"""Lambda cleaner - deletes all Lambda functions and layers.

Respects exclusions: functions using excluded IAM roles are skipped.
"""

from cleaners.base import BaseCleaner
from exclusions import EXCLUDED_IAM_ROLES


class LambdaCleaner(BaseCleaner):
    service_name = "lambda"
    display_name = "Lambda Functions"

    def clean(self):
        client = self.get_client()
        self._delete_functions(client)
        self._delete_layers(client)
        self._delete_event_source_mappings(client)

    def _delete_functions(self, client):
        """Delete all Lambda functions, skipping those using excluded roles."""
        paginator = client.get_paginator("list_functions")
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                func_name = func["FunctionName"]
                func_role = func.get("Role", "")

                # Skip functions that use an excluded IAM role
                role_name = func_role.split("/")[-1] if "/" in func_role else ""
                if role_name in EXCLUDED_IAM_ROLES:
                    self.log_skip(
                        "Lambda Function",
                        func_name,
                        f"uses excluded role {role_name}",
                    )
                    continue

                try:
                    if not self.dry_run:
                        client.delete_function(FunctionName=func_name)
                    self.log_delete("Lambda Function", func_name)
                except Exception as e:
                    self.log_error(f"Could not delete function {func_name}", e)

    def _delete_layers(self, client):
        """Delete all Lambda layers and their versions."""
        paginator = client.get_paginator("list_layers")
        for page in paginator.paginate():
            for layer in page.get("Layers", []):
                layer_name = layer["LayerName"]
                try:
                    # Delete all versions of the layer
                    ver_paginator = client.get_paginator("list_layer_versions")
                    for ver_page in ver_paginator.paginate(LayerName=layer_name):
                        for version in ver_page.get("LayerVersions", []):
                            ver_num = version["Version"]
                            if not self.dry_run:
                                client.delete_layer_version(
                                    LayerName=layer_name, VersionNumber=ver_num
                                )
                    self.log_delete("Lambda Layer", layer_name)
                except Exception as e:
                    self.log_error(f"Could not delete layer {layer_name}", e)

    def _delete_event_source_mappings(self, client):
        """Delete all event source mappings."""
        paginator = client.get_paginator("list_event_source_mappings")
        for page in paginator.paginate():
            for mapping in page.get("EventSourceMappings", []):
                uuid = mapping["UUID"]
                try:
                    if not self.dry_run:
                        client.delete_event_source_mapping(UUID=uuid)
                    self.log_delete(
                        "Event Source Mapping",
                        f"{uuid} -> {mapping.get('FunctionArn', 'unknown')}",
                    )
                except Exception as e:
                    self.log_error(f"Could not delete event source mapping {uuid}", e)
