from marshmallow import (
    fields,
    post_load,
    Schema,
    validate,
    validates_schema,
    ValidationError,
)

from .state import State


class MulticloudStackSchema(Schema):
    stack_name = fields.Str(required=True, validate=[validate.Length(min=1)])

    count = fields.Int(required=True, validate=[validate.Range(min=0)])

    count_parameter = fields.Str(required=True)

    weights = fields.Dict(
        required=True, keys=fields.Str(), values=fields.Float()
    )

    @validates_schema
    def validate_weights(self, data, **kwargs):
        total_weight = sum(data["weights"].values())

        if total_weight > 1:
            raise ValidationError(
                f"Total cloud weight over 1 (total weight: {total_weight})",
                "weights",
            )

    @post_load
    def make_multicloud_stack(self, data, **kwargs):
        return MulticloudStack(**data)


class MulticloudStackListSchema(Schema):
    stacks = fields.List(fields.Nested(MulticloudStackSchema))


class MulticloudStack(State):
    schema = MulticloudStackSchema
    list_schema = MulticloudStackListSchema

    def __init__(self, stack_name, count, count_parameter, weights={}):
        self.stack_name = stack_name
        self.count = count
        self.count_parameter = count_parameter

        self.weights = weights

    def __eq__(self, other):
        return (
            self.stack_name == other.stack_name
            and self.count == other.count
            and self.count_parameter == other.count_parameter
            and self.weights == other.weights
        )
