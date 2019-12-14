from prettytable import PrettyTable


class StackTable(PrettyTable):
    def __init__(self, multicloud_stack):
        super().__init__()

        self.field_names = ["Attribute", "Value"]

        self.align["Attribute"] = "r"
        self.align["Value"] = "l"

        self.add_row(["Name", multicloud_stack.stack_name])
        self.add_row(["Desired count", multicloud_stack.count])
        self.add_row(["Count parameter", multicloud_stack.count_parameter])

        weights = []
        for cloud_name, weight in multicloud_stack.weights.items():
            weight = round(weight * 100, 1)
            weights.append(f"{cloud_name} ({weight}%)")
        self.add_row(["Weights", "\n".join(weights)])


class StacksTable(PrettyTable):
    def __init__(self, multicloud_stack_list):
        super().__init__()

        self.field_names = [
            "Stack name",
            "Desired count",
            "Count parameter",
            "Clouds",
        ]

        self.align = "l"

        for multicloud_stack in multicloud_stack_list["stacks"]:
            self.add_row(
                [
                    multicloud_stack.stack_name,
                    multicloud_stack.count,
                    multicloud_stack.count_parameter,
                    ", ".join(multicloud_stack.weights.keys()),
                ]
            )
