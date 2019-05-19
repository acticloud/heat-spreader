class BackendException(Exception):
    """Backend exception."""


class NotFoundException(BackendException):
    def __init__(self, name):
        self.name = name
