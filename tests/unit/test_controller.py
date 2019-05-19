from unittest.mock import Mock

import pytest
from heatclient import exc as heat_exc

from heatspreader.config.config import Config
from heatspreader.service.controller import Controller
from heatspreader.service.healthcheck import (
    CloudStatus,
    Healthcheck,
    StackStatus,
)
from heatspreader.state import MulticloudStack


class FakeHeatStack:
    def __init__(self, count_parameter, count):
        self.parameters = {count_parameter: count}

    def assertCount(self, count):
        assert self.parameters[list(self.parameters.keys())[0]] == count


class FakeHeatClient:
    def __init__(self, fake_stacks):
        self.fake_stacks = fake_stacks

        self.stacks = Mock()
        self.stacks.get.side_effect = self._get
        self.stacks.update.side_effect = self._update

    def _get(self, stack_id):
        try:
            return self.fake_stacks[stack_id]
        except KeyError:
            raise heat_exc.HTTPNotFound()

    def _update(self, stack_id, existing, parameters):
        try:
            self.fake_stacks[stack_id].parameters = parameters
        except KeyError:
            raise heat_exc.HTTPNotFound()


class FakeHeatClients(dict):
    def __init__(self, initial_state={}):
        for cloud_name, fake_stacks in initial_state.items():
            self[cloud_name] = FakeHeatClient(fake_stacks)


def multicloud_stack_from_clouds(
    clouds, name="stack", count=0, parameter="param"
):
    weights = {}

    for cloud_name, cloud in clouds.items():
        weights[cloud_name] = cloud["weight"] if "weight" in cloud else 0.0

    return MulticloudStack(
        stack_name=name,
        count=count,
        count_parameter=parameter,
        weights=weights,
    )


class TestController:
    @pytest.fixture
    def setup_controller(self):
        def _setup_controller(clouds, multicloud_stacks):
            config = Config(None, None, clouds=clouds)

            healthcheck = Healthcheck()

            for multicloud_stack in multicloud_stacks:
                for cloud_name, cloud in multicloud_stack.weights.items():
                    if "unhealthy" in clouds[cloud_name]:
                        healthcheck.cloud(
                            cloud_name, status=CloudStatus.UNREACHABLE
                        )
                    else:
                        healthcheck.cloud(
                            cloud_name, status=CloudStatus.HEALTHY
                        )
                        healthcheck.stack(
                            multicloud_stack,
                            cloud_name,
                            status=StackStatus.HEALTHY,
                        )

            controller = Controller(config, Mock(), healthcheck)

            controller._running = True

            return controller

        return _setup_controller

    @pytest.mark.parametrize(
        "expected, stack_name, cloud_name, parameter, heat_client_state",
        [
            # Normal
            (
                1,
                "stack",
                "cloud_1",
                "param",
                {"cloud_1": {"stack": FakeHeatStack("param", 1)}},
            ),
            # Missing parameter
            (
                None,
                "stack",
                "cloud_1",
                "param",
                {"cloud_1": {"stack": FakeHeatStack("other_param", 1)}},
            ),
            # Not found
            (
                None,
                "stack",
                "cloud_1",
                "param",
                {"cloud_1": {"other_stack": FakeHeatStack("param", 1)}},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_current_count(
        self,
        setup_controller,
        expected,
        stack_name,
        cloud_name,
        parameter,
        heat_client_state,
    ):
        clouds = {cloud_name: {}}

        multicloud_stack = multicloud_stack_from_clouds(
            clouds, name=stack_name, parameter=parameter
        )

        controller = setup_controller(clouds, [multicloud_stack])

        controller._heat_clients = FakeHeatClients(heat_client_state)

        actual = await controller._get_current_count(
            multicloud_stack, cloud_name
        )

        assert actual == expected

    @pytest.mark.parametrize(
        "expected, clouds",
        [
            # No clouds
            (0, {}),
            # Healthy
            (0, {"cloud_1": {"weight": 1}}),
            # Unhealthy
            (0, {"cloud_1": {"weight": 1, "unhealthy": True}}),
            # Single healthy, single unhealthy
            (
                0.5,
                {
                    "cloud_1": {"weight": 0.5},
                    "cloud_2": {"weight": 0.5, "unhealthy": True},
                },
            ),
            # Single healthy, multiple unhealthy
            (
                0.5,
                {
                    "cloud_1": {"weight": 0.5},
                    "cloud_2": {"weight": 0.3, "unhealthy": True},
                    "cloud_3": {"weight": 0.2, "unhealthy": True},
                },
            ),
            # Multiple healthy, multiple unhealthy
            (
                0.25,
                {
                    "cloud_1": {"weight": 0.2},
                    "cloud_2": {"weight": 0.3},
                    "cloud_3": {"weight": 0.2, "unhealthy": True},
                    "cloud_4": {"weight": 0.3, "unhealthy": True},
                },
            ),
        ],
    )
    def test_get_failover_weight(self, setup_controller, expected, clouds):
        multicloud_stack = multicloud_stack_from_clouds(clouds)

        controller = setup_controller(clouds, [multicloud_stack])

        assert controller._get_failover_weight(multicloud_stack) == expected

    @pytest.mark.parametrize(
        "count, clouds, expected",
        [
            # Simple
            (1, {"cloud_1": {"weight": 1.0}}, {"cloud_1": 1}),
            # Multiple
            (
                4,
                {"cloud_1": {"weight": 0.25}, "cloud_2": {"weight": 0.75}},
                {"cloud_1": 1, "cloud_2": 3},
            ),
            # Rounding
            (
                5,
                {
                    "cloud_1": {"weight": 0.0},
                    "cloud_2": {"weight": 0.2},
                    "cloud_3": {"weight": 0.3},
                },
                {"cloud_1": 0, "cloud_2": 1, "cloud_3": 2},
            ),
            # Failover
            (
                10,
                {
                    "cloud_1": {"weight": 0.6},
                    "cloud_2": {"weight": 0.2},
                    "cloud_3": {"weight": 0.2, "unhealthy": True},
                },
                {"cloud_1": 7, "cloud_2": 3, "cloud_3": 0},
            ),
            # Failover + Rounding
            (
                10,
                {
                    "cloud_1": {"weight": 0.4},
                    "cloud_2": {"weight": 0.3},
                    "cloud_3": {"weight": 0.2, "unhealthy": True},
                    "cloud_4": {"weight": 0.1, "unhealthy": True},
                },
                {"cloud_1": 6, "cloud_2": 5, "cloud_3": 0, "cloud_4": 0},
            ),
        ],
    )
    def test_get_desired_counts(
        self, setup_controller, count, clouds, expected
    ):
        multicloud_stack = multicloud_stack_from_clouds(clouds, count=count)

        controller = setup_controller(clouds, [multicloud_stack])

        assert controller._get_desired_counts(multicloud_stack) == expected

    @pytest.mark.parametrize(
        "clouds, expected_plan",
        [
            # Satisfied
            (
                {"cloud_1": {"current": 1, "desired": 1}},
                {"scaleup": {}, "scaledown": {}},
            ),
            # Scale up
            (
                {"cloud_1": {"current": 0, "desired": 1}},
                {"scaleup": {"cloud_1": (0, 1)}, "scaledown": {}},
            ),
            # Scale down
            (
                {"cloud_1": {"current": 1, "desired": 0}},
                {"scaleup": {}, "scaledown": {"cloud_1": (1, 0)}},
            ),
            # Unhealthy
            (
                {"cloud_1": {"current": 0, "desired": 1, "unhealthy": True}},
                {"scaleup": {}, "scaledown": {}},
            ),
            # Current = None
            (
                {"cloud_1": {"current": None, "desired": 0}},
                {"scaleup": {}, "scaledown": {}},
            ),
            # Mix
            (
                {
                    "cloud_1": {"current": 1, "desired": 0},
                    "cloud_2": {"current": 0, "desired": 1},
                    "cloud_3": {"current": 2, "desired": 1},
                    "cloud_4": {"current": 1, "desired": 2},
                    "cloud_5": {"current": 1, "desired": 1},
                    "cloud_6": {"current": 1, "desired": 0, "unhealthy": True},
                    "cloud_7": {"current": None, "desired": 1},
                },
                {
                    "scaleup": {"cloud_2": (0, 1), "cloud_4": (1, 2)},
                    "scaledown": {"cloud_1": (1, 0), "cloud_3": (2, 1)},
                },
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_update_plan(
        self, setup_controller, expected_plan, clouds
    ):
        multicloud_stack = multicloud_stack_from_clouds(clouds)

        controller = setup_controller(clouds, [multicloud_stack])

        async def _get_current_counts(*args, **kwargs):
            return {
                cloud_name: cloud["current"]
                for cloud_name, cloud in clouds.items()
            }

        def _get_desired_counts(*args, **kwargs):
            return {
                cloud_name: cloud["desired"]
                for cloud_name, cloud in clouds.items()
            }

        controller._get_current_counts = _get_current_counts

        controller._get_desired_counts = _get_desired_counts

        actual_plan = await controller.get_update_plan(multicloud_stack)

        assert actual_plan == expected_plan

    @pytest.mark.parametrize(
        "plan",
        [
            # Scale up
            ({"scaleup": {"cloud_1": (0, 1)}, "scaledown": {}}),
            # Scale down
            ({"scaleup": {}, "scaledown": {"cloud_1": (1, 0)}}),
        ],
    )
    @pytest.mark.asyncio
    async def test_scale_multicloud_stack(self, setup_controller, plan):
        cloud_names = list(plan["scaleup"].keys()) + list(
            plan["scaledown"].keys()
        )
        clouds = {cloud_name: {} for cloud_name in cloud_names}

        multicloud_stack = multicloud_stack_from_clouds(clouds)

        controller = setup_controller(clouds, [multicloud_stack])

        heat_client_state = {}
        expected = {}
        for cloud_name, (current, desired) in plan["scaleup"].items():
            heat_client_state[cloud_name] = {
                multicloud_stack.stack_name: FakeHeatStack(
                    multicloud_stack.count_parameter, current
                )
            }
            expected[cloud_name] = {multicloud_stack.stack_name: desired}
        for cloud_name, (current, desired) in plan["scaledown"].items():
            heat_client_state[cloud_name] = {
                multicloud_stack.stack_name: FakeHeatStack(
                    multicloud_stack.count_parameter, current
                )
            }
            expected[cloud_name] = {multicloud_stack.stack_name: desired}

        controller._heat_clients = FakeHeatClients(heat_client_state)

        await controller.scale_multicloud_stack(multicloud_stack, plan)

        for cloud_name, expected_counts in expected.items():
            for stack_name, expected_count in expected_counts.items():
                fake_stack = heat_client_state[cloud_name][stack_name]
                fake_stack.assertCount(expected_count)
