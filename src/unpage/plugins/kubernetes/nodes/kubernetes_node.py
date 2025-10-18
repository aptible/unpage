from unpage.plugins.kubernetes.nodes.utils import label_key_value_to_node_id

from .base import KubernetesBaseNode


class KubernetesNode(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
            *[
                label_key_value_to_node_id(key, value)
                for key, value in self.raw_data.get("metadata", {}).get("labels", {}).items()
            ],
        ]

        # For GKE nodes, extract the node pool name from the node name
        # GKE node names follow the pattern: gk3-{cluster}-{pool}-{hash}-{random}
        # e.g., "gk3-online-boutique-pool-1-b46cb125-t4tv" -> pool-1
        # e.g., "gk3-online-boutique-nap-15nmc7v2-bf7bdba2-nwjt" -> nap-15nmc7v2
        metadata = self.raw_data.get("metadata", {})
        node_name = metadata.get("name", "")
        if node_name.startswith("gk3-"):
            # Split the node name and try to extract pool identifier
            parts = node_name.split("-")
            # Pattern: gk3-{cluster-parts}-{pool-parts}-{hash}-{random}  # noqa: ERA001
            # We need to find where the pool name starts
            # Common patterns: "pool-1", "pool-2", "default-pool", "nap-xxx"
            if len(parts) >= 4:
                # Try to reconstruct the pool name
                # Look for pool indicators
                for i in range(1, len(parts) - 2):
                    part = parts[i]
                    if part in ["pool", "nap", "default"] or part.startswith("pool"):
                        # Found potential pool start, collect pool parts
                        pool_parts = [part]
                        # Check if next part is a number or continuation
                        if i + 1 < len(parts) - 2:
                            next_part = parts[i + 1]
                            # If it's a number or starts with a number, it's part of pool name
                            if next_part.isdigit() or (
                                len(next_part) > 0 and next_part[0].isdigit()
                            ):
                                pool_parts.append(next_part)
                            # If it looks like a hash (8+ hex chars), it's the suffix
                            elif len(next_part) >= 8 and all(
                                c in "0123456789abcdef" for c in next_part
                            ):
                                pass  # This is the hash, not part of pool name
                            # Otherwise might be part of pool name (like "nap-15nmc7v2")
                            else:
                                pool_parts.append(next_part)

                        pool_name = "-".join(pool_parts)
                        identifiers.append(pool_name)
                        break

        return identifiers

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
