from abc import ABC, abstractmethod


class Command(ABC):
    def __init__(self, parser):
        pass

    @property
    @abstractmethod
    def name(self):
        raise NotImplementedError()

    @property
    @abstractmethod
    def help(self):
        raise NotImplementedError()

    @abstractmethod
    async def run(self, **kwargs):
        raise NotImplementedError()
