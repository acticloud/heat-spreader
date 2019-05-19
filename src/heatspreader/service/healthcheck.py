from collections import defaultdict
from enum import Enum, auto

import structlog

log = structlog.getLogger(__name__)


class CloudStatus(Enum):
    NOT_CHECKED = auto()
    HEALTHY = auto()
    UNREACHABLE = auto()


class StackStatus(Enum):
    NOT_CHECKED = auto()
    HEALTHY = auto()
    NOT_FOUND = auto()
    MISSING_COUNT_PARAMETER = auto()


class CloudHealth:
    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        if status == self._status:
            return

        self.log.info("healthcheck_cloud_status_updated", status=status.name)

        self._status = status

    def __init__(self, name):
        self.log = log.bind(cloud_name=name)

        self._status = CloudStatus.NOT_CHECKED


class StackHealth:
    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        if status == self._status:
            return

        self.log.info("healthcheck_stack_status_updated", status=status.name)

        self._status = status

    def __init__(self, name, cloud_name):
        self.log = log.bind(stack_name=name, cloud_name=cloud_name)

        self._status = CloudStatus.NOT_CHECKED


class Healthcheck:
    def __init__(self):
        self.clouds = {}
        self.stacks = defaultdict(dict)

    def cloud(self, cloud_name, status=None):
        try:
            cloud = self.clouds[cloud_name]
        except KeyError:
            cloud = CloudHealth(cloud_name)
            self.clouds[cloud_name] = cloud

        if status is not None:
            cloud.status = status

        return cloud.status

    def stack(self, multicloud_stack, cloud_name, status=None):
        cloud_stacks = self.stacks[cloud_name]

        try:
            stack = cloud_stacks[multicloud_stack.stack_name]
        except KeyError:
            stack = StackHealth(multicloud_stack.stack_name, cloud_name)
            self.stacks[cloud_name][multicloud_stack.stack_name] = stack

        if status is not None:
            stack.status = status

        return stack.status

    def stack_is_available(self, multicloud_stack, cloud_name):
        cs = self.cloud(cloud_name)
        ss = self.stack(multicloud_stack, cloud_name)
        return cs == CloudStatus.HEALTHY and ss == StackStatus.HEALTHY
