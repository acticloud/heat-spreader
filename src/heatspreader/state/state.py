from abc import ABC


class State(ABC):
    @classmethod
    def load(cls, data):
        if not cls.schema:
            raise NotImplementedError("Missing schema")

        return cls.schema().load(data)

    @classmethod
    def load_list(cls, data):
        if not cls.list_schema:
            raise NotImplementedError("Missing list schema")

        return cls.list_schema().load(data)

    def dump(self):
        if not self.schema:
            raise NotImplementedError("Missing schema")

        return self.schema().dump(self)

    def dumps(self):
        if not self.schema:
            raise NotImplementedError("Missing schema")

        return self.schema().dumps(self)

    @classmethod
    def dump_list(cls, list_data):
        if not cls.list_schema:
            raise NotImplementedError("Missing list schema")

        return cls.list_schema().dump(list_data)

    @classmethod
    def dumps_list(cls, list_data):
        if not cls.list_schema:
            raise NotImplementedError("Missing list schema")

        return cls.list_schema().dumps(list_data)

    def validate(self):
        if not self.schema:
            raise NotImplementedError("Missing schema")

        return self.schema().validate(self.dump())
