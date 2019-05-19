from marshmallow.exceptions import (
    ValidationError as MarshmallowValidationError,
)

from .client.exceptions import *
from .config.exceptions import *
from .store.backend.exceptions import *
from .store.exceptions import *


class ValidationError(MarshmallowValidationError):
    pass
