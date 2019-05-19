class WeightNotFound(Exception):
    def __init__(self, stack_name, cloud_name):
        super().__init__(
            f"Weight for cloud '{cloud_name}' not found in multicloud stack: "
            f"{stack_name}"
        )
