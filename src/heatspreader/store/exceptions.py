class MulticloudStackNotFound(Exception):
    def __init__(self, stack_name):
        super().__init__(f"Multicloud stack not found: {stack_name}")
