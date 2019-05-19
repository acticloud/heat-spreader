import json
import sys


def print_error(msg):
    print(msg, file=sys.stderr)


def validation_error_formatter(exc):
    return json.dumps(exc.messages, indent=4, sort_keys=True)
