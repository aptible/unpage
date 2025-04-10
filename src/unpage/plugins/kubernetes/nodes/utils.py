def label_key_value_to_node_id(key: str, value: str) -> str:
    """
    Convert a Kubernetes label key and value to a node id.
    """
    return f"label://{key}={value}"
