from unpage.plugins.kubernetes.nodes.utils import label_key_value_to_node_id

from .base import KubernetesBaseNode


class KubernetesNode(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            *[
                label_key_value_to_node_id(key, value)
                for key, value in self.raw_data.get("metadata", {}).get("labels", {}).items()
            ],
        ]

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
            *[
                (a["address"], "running_on")
                for a in self.raw_data.get("status", {}).get("addresses", [])
                if "address" in a
            ],
        ]

        # Add provider ID reference for cross-platform linking
        provider_id = self.raw_data.get("spec", {}).get("providerID")
        if provider_id:
            # Handle Azure provider IDs (azure:///subscriptions/...)
            if provider_id.startswith("azure://"):
                # Strip azure:// prefix to get the resource ID
                azure_resource_id = provider_id.replace("azure://", "")
                # Add both original case and lowercase versions for matching
                references.append((azure_resource_id, "runs_on_azure_vm"))
                references.append((azure_resource_id.lower(), "runs_on_azure_vm"))
            # Handle AWS provider IDs (aws:///zone/instance-id)
            elif provider_id.startswith("aws://"):
                # AWS format: aws:///us-west-2a/i-1234567890abcdef0
                parts = provider_id.replace("aws://", "").split("/")
                if len(parts) >= 2:
                    instance_id = parts[-1]
                    references.append((instance_id, "runs_on_aws_instance"))
            # Handle GCP provider IDs
            elif provider_id.startswith("gce://"):
                # GCP format: gce://project/zone/instance-name
                references.append((provider_id, "runs_on_gcp_instance"))

        return references
