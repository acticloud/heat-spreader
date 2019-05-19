import json
import os
import subprocess
import time
import yaml
import warnings

import openstack
import pytest

SERVER_STARTUP_TIMEOUT = 10
SERVER_SHUTDOWN_TIMEOUT = 30
STACK_DELETE_TIMEOUT = 60
SCALE_TIMEOUT = 120

TEST_STACK_NAME = "e2e-test"

DEFAULT_ENV = os.environ.copy()
DEFAULT_ENV["HEAT_SPREADER_LOG_LEVEL"] = "DEBUG"

E2E_TEST_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_PATH = os.path.join(E2E_TEST_DIR, "log")
SERVER_CONFIG_FILE = os.path.join(E2E_TEST_DIR, "config-server.yaml")
CLIENT_CONFIG_FILE = os.path.join(E2E_TEST_DIR, "config-client.yaml")
SERVER_LOG_FILE = os.path.join(LOG_PATH, "server.log")
CLIENT_LOG_FILE = os.path.join(LOG_PATH, "client.log")

HEAT_TEMPLATES_PATH = os.path.join(E2E_TEST_DIR, "hot")
HEAT_SERVERS_TEMPLATE_FILE = os.path.join(HEAT_TEMPLATES_PATH, "servers.yaml")


class Timeout:
    @property
    def exceeded(self):
        return (time.time() - self.start_time) > self.timeout

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, type, value, traceback):
        pass


class E2EServerTest:
    @classmethod
    def setup_class(cls):
        cls._start_server()

    @classmethod
    def teardown_class(cls):
        cls._stop_server()

    @classmethod
    def _start_server(cls):
        cls.server_proc = subprocess.Popen(
            ["heat-spreader", "run"],
            env={
                **DEFAULT_ENV,
                **{
                    "HEAT_SPREADER_CONFIG_FILE": SERVER_CONFIG_FILE,
                    "HEAT_SPREADER_LOG_FILE": SERVER_LOG_FILE,
                },
            },
        )

        with Timeout(SERVER_STARTUP_TIMEOUT) as timeout_ctx:
            while True:
                proc = subprocess.run(
                    (
                        f"lsof -Pan -p {cls.server_proc.pid} -i 2>/dev/null | "
                        "tail -n 1 | awk '{print $9}' | cut -d':' -f2"
                    ),
                    capture_output=True,
                    shell=True,
                )
                try:
                    cls.server_port = int(proc.stdout)
                    break
                except ValueError:
                    pass

                if timeout_ctx.exceeded:
                    raise Exception(
                        "Timeout while waiting for server to start"
                    )

                time.sleep(1)

    @classmethod
    def _stop_server(cls):
        cls.server_proc.terminate()
        try:
            cls.server_proc.wait(timeout=SERVER_SHUTDOWN_TIMEOUT)
        except subprocess.TimeoutExpired:
            cls.server_proc.kill()
            warnings.warn("Failed to terminate server gracefully")

    def client_command(
        self,
        cmd,
        returncode=0,
        stdout=b"",
        stdout_json_decode=True,
        stderr=b"",
    ):
        proc = subprocess.run(
            ["heat-spreader"] + cmd,
            capture_output=True,
            env={
                **DEFAULT_ENV,
                **{
                    "HEAT_SPREADER_CONFIG_FILE": CLIENT_CONFIG_FILE,
                    "HEAT_SPREADER_LOG_FILE": CLIENT_LOG_FILE,
                    "HEAT_SPREADER_BACKEND_REMOTE_PORT": str(self.server_port),
                },
            },
        )
        assert proc.returncode == returncode
        if stdout_json_decode:
            assert json.loads(proc.stdout) == stdout
        else:
            assert proc.stdout == stdout
        assert proc.stderr == stderr


class TestEndToEnd(E2EServerTest):
    def test_list(self):
        self.client_command(cmd=["list", "--json"], stdout={"stacks": []})


@pytest.mark.skipif(
    "OS_CLIENT_CONFIG_FILE" not in os.environ,
    reason="Missing OS_CLIENT_CONFIG_FILE environment variable",
)
class TestEndToEndWithClouds(E2EServerTest):
    @classmethod
    def setup_class(cls):
        cls._parse_clouds()
        cls._setup_openstack_connections()
        cls._create_stacks()

        super().setup_class()

    @classmethod
    def teardown_class(cls):
        super().teardown_class()

        cls._delete_stacks()

    @classmethod
    def _parse_clouds(cls):
        with open(SERVER_CONFIG_FILE, "r") as server_config_file:
            server_config = yaml.safe_load(server_config_file)
        cls.clouds = server_config["clouds"]

    @classmethod
    def _setup_openstack_connections(cls):
        cls.openstack_connections = {
            cloud_name: openstack.connect(cloud=cloud_name)
            for cloud_name in cls.clouds
        }

    @classmethod
    def _create_stacks(cls):
        for conn in cls.openstack_connections.values():
            conn.create_stack(
                name=TEST_STACK_NAME,
                template_file=HEAT_SERVERS_TEMPLATE_FILE,
                count=0,
                flavor="small",
                image="cirros",
                network="private",
            )

    @classmethod
    def _delete_stacks(cls):
        # NOTE: Letting things settle before deleting the stacks.
        #       There seem to be some kind of race happening when deleting
        #       them too quickly causing the stack(s) to end up in a
        #       DELETE_FAILED state. A probable cause is some resources are not
        #       done updating even though the stack says status
        #       UPDATE_COMPLETE.
        time.sleep(30)

        for conn in cls.openstack_connections.values():
            conn.delete_stack(TEST_STACK_NAME)

        conns = dict(cls.openstack_connections.items())

        with Timeout(STACK_DELETE_TIMEOUT) as timeout_ctx:
            while True:
                for cloud_name, conn in conns.copy().items():
                    stack = conn.get_stack(TEST_STACK_NAME)
                    if stack is None:
                        del conns[cloud_name]

                if not conns:
                    break

                if timeout_ctx.exceeded:
                    warnings.warn(
                        "timeout while waiting for stacks to be deleted"
                    )
                    break

                time.sleep(1)

    def _wait_for_stack_status(self, action, status, timeout_ctx):
        conns = dict(self.openstack_connections.items())

        while True:
            for cloud_name, client in conns.copy().items():
                stack = client.get_stack(TEST_STACK_NAME)

                if stack.action == action and stack.status == status:
                    del conns[cloud_name]

            if not conns:
                break

            if timeout_ctx.exceeded:
                pytest.fail(
                    f"timeout while waiting for stack status '{status}', "
                    f"last stack status check was '{stack.status}', cannot "
                    f"continue test + {stack['stack_status']}"
                )

            time.sleep(1)

    def test_scaling(self):
        expected = {
            "stack_name": TEST_STACK_NAME,
            "count": 0,
            "count_parameter": "count",
            "weights": {},
        }

        # Sanity check remote stacks state

        for client in self.openstack_connections.values():
            stack = client.get_stack(TEST_STACK_NAME)
            assert stack is not None
            assert expected["count_parameter"] in stack.parameters
            assert (
                int(stack.parameters[expected["count_parameter"]])
                == expected["count"]
            )

        # Add multicloud stack

        self.client_command(
            cmd=[
                "add",
                TEST_STACK_NAME,
                "--count",
                str(expected["count"]),
                "--parameter",
                expected["count_parameter"],
                "--json",
            ],
            stdout=expected,
        )

        # Add cloud 1 weight

        expected["weights"][self.clouds[0]] = 0.5

        self.client_command(
            cmd=[
                "weight",
                "set",
                TEST_STACK_NAME,
                self.clouds[0],
                "--weight",
                str(expected["weights"][self.clouds[0]]),
                "--json",
            ],
            stdout=expected,
        )

        # Add cloud 2 weight

        expected["weights"][self.clouds[1]] = 0.5

        self.client_command(
            cmd=[
                "weight",
                "set",
                TEST_STACK_NAME,
                self.clouds[1],
                "--weight",
                str(expected["weights"][self.clouds[1]]),
                "--json",
            ],
            stdout=expected,
        )

        # Scale out

        expected["count"] = 4

        self.client_command(
            cmd=[
                "update",
                TEST_STACK_NAME,
                "--count",
                str(expected["count"]),
                "--json",
            ],
            stdout=expected,
        )

        # Verify scale out propagation

        with Timeout(SCALE_TIMEOUT) as timeout_ctx:
            self._wait_for_stack_status(
                action="UPDATE", status="COMPLETE", timeout_ctx=timeout_ctx
            )

            conns = dict(self.openstack_connections.items())
            while True:
                for cloud_name, client in conns.copy().items():
                    stack = client.get_stack(TEST_STACK_NAME)

                    actual_count = float(
                        stack.parameters[expected["count_parameter"]]
                    )
                    expected_count = float(
                        expected["count"] * expected["weights"][cloud_name]
                    )

                    if actual_count == expected_count:
                        del conns[cloud_name]

                if not conns:
                    break

                if timeout_ctx.exceeded:
                    assert (
                        conns.keys() == []
                    ), "timeout while waiting for scale out"

                time.sleep(1)

        # Offload

        expected["weights"][self.clouds[0]] = 0.25

        self.client_command(
            cmd=[
                "weight",
                "set",
                TEST_STACK_NAME,
                self.clouds[0],
                "--weight",
                str(expected["weights"][self.clouds[0]]),
                "--json",
            ],
            stdout=expected,
        )

        expected["weights"][self.clouds[1]] = 0.75

        self.client_command(
            cmd=[
                "weight",
                "set",
                TEST_STACK_NAME,
                self.clouds[1],
                "--weight",
                str(expected["weights"][self.clouds[1]]),
                "--json",
            ],
            stdout=expected,
        )

        # Verify offloading

        with Timeout(SCALE_TIMEOUT) as timeout_ctx:
            self._wait_for_stack_status(
                action="UPDATE", status="COMPLETE", timeout_ctx=timeout_ctx
            )

            conns = dict(self.openstack_connections.items())
            while True:
                for cloud_name, client in conns.copy().items():
                    stack = client.get_stack(TEST_STACK_NAME)

                    actual_count = float(
                        stack.parameters[expected["count_parameter"]]
                    )
                    expected_count = float(
                        expected["count"] * expected["weights"][cloud_name]
                    )

                    if actual_count == expected_count:
                        del conns[cloud_name]

                if not conns:
                    break

                if timeout_ctx.exceeded:
                    assert (
                        conns.keys() == []
                    ), "timeout while waiting for offloading"

                time.sleep(1)

        # Scale in

        expected["count"] = 0

        self.client_command(
            cmd=[
                "update",
                TEST_STACK_NAME,
                "--count",
                str(expected["count"]),
                "--json",
            ],
            stdout=expected,
        )

        # Verify scale in

        with Timeout(SCALE_TIMEOUT) as timeout_ctx:
            self._wait_for_stack_status(
                action="UPDATE", status="COMPLETE", timeout_ctx=timeout_ctx
            )

            conns = dict(self.openstack_connections.items())
            while True:
                for cloud_name, client in conns.copy().items():
                    stack = client.get_stack(TEST_STACK_NAME)

                    actual_count = float(
                        stack.parameters[expected["count_parameter"]]
                    )

                    if actual_count == 0:
                        del conns[cloud_name]

                if not conns:
                    break

                if timeout_ctx.exceeded:
                    assert (
                        conns.keys() == []
                    ), "timeout while waiting for scale in"

                time.sleep(1)
