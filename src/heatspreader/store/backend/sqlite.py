import peewee
from playhouse.shortcuts import model_to_dict
import structlog

from .exceptions import BackendException, NotFoundException

from .abstract_store_backend import AbstractStoreBackend

log = structlog.getLogger(__name__)

db = peewee.SqliteDatabase(None, pragmas=(("foreign_keys", "on"),))


class BaseModel(peewee.Model):
    class Meta:
        database = db


class MulticloudStackModel(BaseModel):
    stack_name = peewee.CharField(primary_key=True)
    count = peewee.IntegerField()
    count_parameter = peewee.CharField()


class WeightModel(BaseModel):
    multicloud_stack = peewee.ForeignKeyField(
        MulticloudStackModel, backref="weights", on_delete="CASCADE"
    )
    cloud_name = peewee.CharField()
    weight = peewee.FloatField()

    class Meta:
        primary_key = peewee.CompositeKey("multicloud_stack", "cloud_name")


def _multicloud_stack_model_to_dict(multicloud_stack_model):
    multicloud_stack_dict = model_to_dict(
        multicloud_stack_model, backrefs=True
    )

    weights = {}
    for weight in multicloud_stack_dict["weights"]:
        weights[weight["cloud_name"]] = weight["weight"]
    multicloud_stack_dict["weights"] = weights

    return multicloud_stack_dict


def db_error_handler(f):
    async def wrapper(*args, **kwargs):
        if db.is_closed():
            raise RuntimeError("database session closed")

        return await f(*args, **kwargs)

    return wrapper


class StoreBackend(AbstractStoreBackend):
    def __init__(self, config):
        super().__init__(config)

        self._log = log.bind(database=config.database)

        db.init(config.database)

        self._log.debug("backend_sqlite_connect")

        try:
            db.connect()
        except peewee.OperationalError as exc:
            err_msg = f"failed to connect to database: {config.database}"
            raise BackendException(err_msg) from exc

        db.create_tables([MulticloudStackModel, WeightModel])

    async def close(self):
        self._log.debug("backend_sqlite_close")

        db.close()

    @db_error_handler
    async def multicloud_stack_get(self, stack_name):
        try:
            multicloud_stack_model = (
                MulticloudStackModel.select()
                .join(WeightModel, peewee.JOIN.LEFT_OUTER)
                .where((MulticloudStackModel.stack_name == stack_name))
                .get()
            )
        except MulticloudStackModel.DoesNotExist:
            raise NotFoundException(stack_name)

        return _multicloud_stack_model_to_dict(multicloud_stack_model)

    @db_error_handler
    async def multicloud_stack_set(self, multicloud_stack_dict):
        MulticloudStackModel.replace(
            stack_name=multicloud_stack_dict["stack_name"],
            count=multicloud_stack_dict["count"],
            count_parameter=multicloud_stack_dict["count_parameter"],
        ).execute()

        multicloud_stack_model = MulticloudStackModel.get(
            stack_name=multicloud_stack_dict["stack_name"]
        )

        for cloud_name, weight in multicloud_stack_dict["weights"].items():
            WeightModel.replace(
                multicloud_stack=multicloud_stack_model,
                cloud_name=cloud_name,
                weight=weight,
            ).execute()

    @db_error_handler
    async def multicloud_stack_list(self):
        return {
            "stacks": [
                _multicloud_stack_model_to_dict(multicloud_stack_model)
                for multicloud_stack_model in MulticloudStackModel.select()
            ]
        }

    @db_error_handler
    async def multicloud_stack_delete(self, stack_name):
        rows_affected = (
            MulticloudStackModel.delete()
            .where(MulticloudStackModel.stack_name == stack_name)
            .execute()
        )

        if rows_affected == 0:
            raise NotFoundException(stack_name)
