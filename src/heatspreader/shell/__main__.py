import asyncio
import os
from pathlib import Path
import traceback

from marshmallow.exceptions import ValidationError
import openstack

from ..config import ConfigParseException, parse_config_file
from ..log import setup_logging

from .helpers import print_error, validation_error_formatter
from .shell import Shell, ShellException

DEFAULT_CONFIG_PATH = Path(Path.home(), ".config/openstack/heat-spreader.yaml")

config_path = os.environ.get("HEAT_SPREADER_CONFIG_FILE", DEFAULT_CONFIG_PATH)
log_json = os.environ.get("HEAT_SPREADER_LOG_JSON", False)
log_level = os.environ.get("HEAT_SPREADER_LOG_LEVEL", "INFO")
log_verbose = os.environ.get("HEAT_SPREADER_LOG_VERBOSE", False)


def main():
    setup_logging(
        log_level=log_level,
        log_verbose=log_verbose,
        log_json=log_json,
        log_file=os.environ.get("HEAT_SPREADER_LOG_FILE", None),
    )

    try:
        config = parse_config_file(config_path)
    except FileNotFoundError:
        print_error(f"Config file not found: {config_path}")
        exit(1)
    except ConfigParseException as exc:
        print_error(f"Config error: {exc}")
        exit(1)
    except ValidationError as exc:
        err_msg = validation_error_formatter(exc)
        print_error(f"Config validation error: {err_msg}")
        exit(1)

    try:
        exit(asyncio.run(Shell(config).run()))
    except openstack.exceptions.ConfigException as exc:
        print_error(f"OpenStack configuration error: {exc}")
        exit(1)
    except ShellException as exc:
        print_error(str(exc))
        exit(1)
    except Exception as exc:
        print_error("Unexpected exception occured: {}".format(exc))
        print_error(traceback.format_exc())
        exit(1)


if __name__ == "__main__":
    main()
