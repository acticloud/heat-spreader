import asyncio
import concurrent.futures
import math

from heatclient.client import Client as HeatClient
from heatclient import exc as heat_exc
import keystoneauth1
import openstack
import structlog

from .healthcheck import CloudStatus, StackStatus

HEAT_VERSION = 1
# TODO: sleep(x - (end - start))
UPDATE_FREQUENCY = 10

log = structlog.getLogger(__name__)

executor = concurrent.futures.ThreadPoolExecutor()


def run_in_executor(f):
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(executor, lambda: f(*args, **kwargs))

    return wrapper


class MissingCountParameter(Exception):
    pass


class WeightCloudNotInConfig(Exception):
    def __init__(self, stack_name, cloud_name):
        pass


def stack_action(fn):
    async def wrapper(controller, multicloud_stack, cloud_name, *args):
        _log = log.bind(
            stack_name=multicloud_stack.stack_name, cloud_name=cloud_name
        )

        try:
            heat_client = controller._get_heat_client(
                multicloud_stack, cloud_name
            )

            value = await fn(
                controller, heat_client, multicloud_stack, cloud_name, *args
            )

            # NOTE: Currently, a successful stack action determines if the
            #       cloud and the stack on said cloud is healthy. This might
            #       not be correct if a stack action is not evaluating all
            #       health conditions.

            controller._healthcheck.cloud(
                cloud_name, status=CloudStatus.HEALTHY
            )

            controller._healthcheck.stack(
                multicloud_stack, cloud_name, status=StackStatus.HEALTHY
            )

            return value
        # TODO: Use OpenStack SDK if/when it supports PATCH
        # except openstack.exceptions.ResourceNotFound:
        except heat_exc.HTTPNotFound:
            _log.warn("stack_not_found")

            controller._healthcheck.stack(
                multicloud_stack, cloud_name, status=StackStatus.NOT_FOUND
            )
        except keystoneauth1.exceptions.connection.ConnectFailure as exc:
            _log.error("cloud_connection_failed")
            # TODO: exc_info on verbose?
            _log.debug(str(exc))

            controller._healthcheck.cloud(
                cloud_name, status=CloudStatus.UNREACHABLE
            )
        except MissingCountParameter:
            _log.error(
                "stack_missing_count_parameter",
                count_parameter=multicloud_stack.count_parameter,
            )

            controller._healthcheck.stack(
                multicloud_stack,
                cloud_name,
                status=StackStatus.MISSING_COUNT_PARAMETER,
            )
        except WeightCloudNotInConfig:
            _log.error("cloud_not_in_config")
        except Exception as exc:
            _log.error("cloud_connection_failed")
            # TODO: exc_info on verbose?
            _log.debug(str(exc))

            controller._healthcheck.cloud(
                cloud_name, status=CloudStatus.UNREACHABLE
            )

    return wrapper


class Controller:
    def __init__(self, config, store, healthcheck):
        self._clouds = config.clouds
        self._store = store
        self._healthcheck = healthcheck

        self._running = False
        self._sleep_task = None

        self._heat_clients = {}

    def _connect(self):
        for cloud_name in self._clouds:
            connection = openstack.connect(cloud=cloud_name)

            self._heat_clients[cloud_name] = HeatClient(
                session=connection.session, version=HEAT_VERSION
            )

            log.info("cloud_connection_created", cloud_name=cloud_name)

    def _get_heat_client(self, multicloud_stack, cloud_name):
        if cloud_name not in self._clouds:
            raise WeightCloudNotInConfig(
                stack_name=multicloud_stack.stack_name, cloud_name=cloud_name
            )

        return self._heat_clients[cloud_name]

    @run_in_executor
    def _get_stack(self, heat_client, stack_name):
        return heat_client.stacks.get(stack_id=stack_name)

    @stack_action
    async def _get_current_count(
        self, heat_client, multicloud_stack, cloud_name
    ):
        stack = await self._get_stack(heat_client, multicloud_stack.stack_name)

        if multicloud_stack.count_parameter not in stack.parameters:
            raise MissingCountParameter()

        return int(stack.parameters[multicloud_stack.count_parameter])

    async def _get_current_counts(self, multicloud_stack):
        counts = {}

        for cloud_name in multicloud_stack.weights.keys():
            if not self._running:
                break

            counts[cloud_name] = await self._get_current_count(
                multicloud_stack, cloud_name
            )

        return counts

    def _get_failover_weight(self, multicloud_stack):
        """
        Calculate failover weight for a multistack.

        For each cloud check if the stack is available, if not add up the
        weight which needs to be distributed to the other stacks.
        """
        healthy = 0
        failover_weight = 0.0

        for cloud_name, weight in multicloud_stack.weights.items():
            if not self._healthcheck.stack_is_available(
                multicloud_stack, cloud_name
            ):
                failover_weight += weight
                continue

            healthy += 1

        return 0 if healthy == 0 else failover_weight / healthy

    def _get_desired_counts(self, multicloud_stack):
        failover_weight = self._get_failover_weight(multicloud_stack)

        counts = {}

        for cloud_name, weight in multicloud_stack.weights.items():
            if not self._running:
                break

            if not self._healthcheck.stack_is_available(
                multicloud_stack, cloud_name
            ):
                counts[cloud_name] = 0
                continue

            weight = round(weight + failover_weight, 3)
            counts[cloud_name] = math.ceil(multicloud_stack.count * weight)

        return counts

    async def get_update_plan(self, multicloud_stack):
        # Begin with determining current state
        current_counts = await self._get_current_counts(multicloud_stack)
        desired_counts = self._get_desired_counts(multicloud_stack)

        # Draft update plan from determined state
        plan = {"scaleup": {}, "scaledown": {}}

        for cloud_name in multicloud_stack.weights.keys():
            if not self._running:
                break

            current_count = current_counts[cloud_name]
            desired_count = desired_counts[cloud_name]

            _log = log.bind(
                stack_name=multicloud_stack.stack_name,
                cloud=cloud_name,
                count_current=current_count,
                count_desired=desired_count,
            )

            # Skipping stack in cloud if it's not healthy
            if not self._healthcheck.stack_is_available(
                multicloud_stack, cloud_name
            ):
                continue

            # If a stack was unhealthy while current count was determined the
            # current count result will be None. If it has become healthy
            # again at this point we still need to skip it until next
            # iteration.
            if current_count is None:
                continue

            if desired_count == current_count:
                _log.debug("stack_count_satisfied")
                continue

            _log.info("stack_count_unsatisfied")

            if current_count < desired_count:
                plan["scaleup"][cloud_name] = (current_count, desired_count)
            else:
                plan["scaledown"][cloud_name] = (current_count, desired_count)

        return plan

    @run_in_executor
    def _update_stack(self, heat_client, multicloud_stack, desired_count):
        # TODO: Handle missing count parameter
        heat_client.stacks.update(
            stack_id=multicloud_stack.stack_name,
            existing=True,
            parameters={multicloud_stack.count_parameter: desired_count},
        )

    @stack_action
    async def _scale_stack(
        self, heat_client, multicloud_stack, cloud_name, desired_count
    ):
        # TODO: Use OpenStack SDK if/when it supports PATCH ("existing")
        # self.connections[cloud_name].update_stack(
        #     name_or_id=multicloud_stack.stack_name,
        #     **{
        #         multicloud_stack.count_parameter: desired_count,
        #     },
        # )

        await self._update_stack(heat_client, multicloud_stack, desired_count)

        log.info(
            "scale_success",
            stack_name=multicloud_stack.stack_name,
            cloud_name=cloud_name,
            count_desired=desired_count,
        )

    async def scale_multicloud_stack(self, multicloud_stack, plan):
        _log = log.bind(stack_name=multicloud_stack.stack_name)

        for cloud_name, (current, desired) in plan["scaleup"].items():
            if not self._running:
                return

            _log.info(
                "scale_up",
                cloud_name=cloud_name,
                count_current=current,
                count_desired=desired,
            )
            await self._scale_stack(multicloud_stack, cloud_name, desired)

        # TODO: Wait for scale up to finish before scale down
        # TODO: Prevent scale down if one or more scale up fails?

        for cloud_name, (current, desired) in plan["scaledown"].items():
            if not self._running:
                return

            _log.info(
                "scale_down",
                cloud_name=cloud_name,
                count_current=current,
                count_desired=desired,
            )
            await self._scale_stack(multicloud_stack, cloud_name, desired)

    async def _sleep(self):
        if not self._running:
            return

        log.debug("controller_sleep_start")

        self._sleep_task = asyncio.create_task(asyncio.sleep(UPDATE_FREQUENCY))

        try:
            await self._sleep_task
        except asyncio.CancelledError:
            log.debug("controller_sleep_cancelled")
            pass
        finally:
            self._sleep_task = None
            log.debug("controller_sleep_end")

    async def run(self):
        log.info("controller_start")

        self._running = True

        self._connect()

        while True:
            if not self._running:
                break

            multicloud_stack_list = await self._store.list()

            for multicloud_stack in multicloud_stack_list["stacks"]:
                plan = await self.get_update_plan(multicloud_stack)
                await self.scale_multicloud_stack(multicloud_stack, plan)

            await self._sleep()

    async def stop(self):
        log.info("controller_stop")

        self._running = False

        if self._sleep_task:
            self._sleep_task.cancel()

    async def force_stop(self):
        log.info("controller_force_stop")

        await self.stop()

        executor.shutdown(wait=False)

        for thread in executor._threads:
            try:
                thread._tstate_lock.release()
            except Exception:
                pass
