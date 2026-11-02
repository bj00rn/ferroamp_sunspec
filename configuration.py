"""Shared command-line and environment configuration."""

import argparse
import os
import sys


def parse_configuration(parser: argparse.ArgumentParser) -> argparse.Namespace:
    provided = {arg.split("=", 1)[0] for arg in sys.argv[1:]}
    for action in parser._actions:
        if action.dest == "help" or provided.intersection(action.option_strings):
            continue
        key = action.dest.upper()
        raw = os.environ.get(key)
        if raw is None:
            continue
        try:
            if isinstance(action, argparse._StoreTrueAction):
                if raw.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                    raise ValueError("expected true/false, 1/0, yes/no, or on/off")
                value = raw.lower() in ("true", "1", "yes", "on")
            else:
                value = action.type(raw) if action.type else raw
            if action.choices is not None and value not in action.choices:
                raise ValueError("not one of the allowed choices")
        except (ValueError, TypeError) as exc:
            parser.error(f"Invalid configuration for {key}: {exc}")
        action.default = value
        action.required = False
    return parser.parse_args()
